// 社保智答/SocialWise 前端交互脚本

class SocialWiseApp {
    constructor() {
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.sessionId = this.generateSessionId();
        this.chatContainer = document.getElementById('chatContainer');
        this.textInput = document.getElementById('textInput');
        this.micButton = document.getElementById('micButton');
        this.recordingIndicator = document.getElementById('recordingIndicator');
        
        this.initializeApp();
    }
    
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    initializeApp() {
        console.log('🚀 社保智答/SocialWise 初始化中...');
        
        // 检查浏览器支持
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showError('您的浏览器不支持语音功能，请使用现代浏览器。');
            return;
        }
        
        // 绑定事件
        this.bindEvents();
        
        console.log('✅ 系统初始化完成');
    }
    
    bindEvents() {
        // 文本输入回车事件
        this.textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendTextMessage();
            }
        });
        
        // 麦克风按钮事件
        this.micButton.addEventListener('click', () => {
            this.toggleRecording();
        });
    }
    
    async toggleRecording() {
        if (this.isRecording) {
            await this.stopRecording();
        } else {
            await this.startRecording();
        }
    }
    
    async startRecording() {
        try {
            console.log('🎤 开始录音...');
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                } 
            });
            
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this.processVoiceInput(audioBlob);
                
                // 停止所有音频轨道
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            // 更新UI
            this.micButton.classList.add('recording');
            this.micButton.innerHTML = '<span class="mic-icon">⏹️</span><span class="mic-text">停止录音</span>';
            this.recordingIndicator.style.display = 'flex';
            
            // 自动停止录音（最长30秒）
            setTimeout(() => {
                if (this.isRecording) {
                    this.stopRecording();
                }
            }, 30000);
            
        } catch (error) {
            console.error('录音启动失败:', error);
            this.showError('无法启动录音功能，请检查麦克风权限。');
        }
    }
    
    async stopRecording() {
        if (!this.isRecording || !this.mediaRecorder) return;
        
        console.log('⏹️ 停止录音...');
        
        this.mediaRecorder.stop();
        this.isRecording = false;
        
        // 更新UI
        this.micButton.classList.remove('recording');
        this.micButton.innerHTML = '<span class="mic-icon">🎤</span><span class="mic-text">点击说话</span>';
        this.recordingIndicator.style.display = 'none';
    }
    
    async processVoiceInput(audioBlob) {
        try {
            console.log('🔄 处理语音输入...');
            this.showTyping();
            
            // 发送音频到ASR服务
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            
            const asrResponse = await fetch('/api/v1/voice/asr', {
                method: 'POST',
                body: formData
            });
            
            if (!asrResponse.ok) {
                throw new Error('语音识别失败');
            }
            
            const asrResult = await asrResponse.json();
            const recognizedText = asrResult.text;
            
            console.log('📝 识别结果:', recognizedText);
            
            if (!recognizedText || recognizedText.trim() === '') {
                this.hideTyping();
                this.showError('未能识别到语音内容，请重试。');
                return;
            }
            
            // 显示用户消息
            this.addMessage('user', recognizedText);
            
            // 发送到问答系统
            await this.sendQuestion(recognizedText);
            
        } catch (error) {
            console.error('语音处理失败:', error);
            this.hideTyping();
            this.showError('语音处理失败，请重试。');
        }
    }
    
    async sendTextMessage() {
        const question = this.textInput.value.trim();
        if (!question) return;
        
        // 清空输入框
        this.textInput.value = '';
        
        // 显示用户消息
        this.addMessage('user', question);
        
        // 发送问题
        await this.sendQuestion(question);
    }
    
    async sendQuestion(question) {
        try {
            console.log('❓ 发送问题:', question);
            this.showTyping();
            
            const response = await fetch('/api/v1/chat/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    question: question,
                    session_id: this.sessionId
                })
            });
            
            if (!response.ok) {
                throw new Error('问答服务异常');
            }
            
            const result = await response.json();
            
            this.hideTyping();
            
            // 显示助手回答
            this.addMessage('assistant', result.answer, {
                confidence: result.confidence,
                sources: result.sources,
                responseTime: result.response_time
            });
            
            // 语音播放回答
            await this.playTextToSpeech(result.answer);
            
        } catch (error) {
            console.error('问答失败:', error);
            this.hideTyping();
            this.showError('抱歉，我暂时无法回答您的问题，请稍后重试。');
        }
    }
    
    async playTextToSpeech(text) {
        try {
            console.log('🔊 播放语音回答...');
            
            const response = await fetch('/api/v1/voice/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text,
                    voice: 'xiaoyan'
                })
            });
            
            if (!response.ok) {
                console.warn('语音合成失败，仅显示文字回答');
                return;
            }
            
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            audio.play().catch(error => {
                console.warn('音频播放失败:', error);
            });
            
            // 清理URL对象
            audio.addEventListener('ended', () => {
                URL.revokeObjectURL(audioUrl);
            });
            
        } catch (error) {
            console.warn('语音播放失败:', error);
        }
    }
    
    addMessage(type, content, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = `${type}-avatar`;
        avatar.textContent = type === 'user' ? '👤' : '🤖';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // 处理消息内容
        const contentP = document.createElement('p');
        contentP.textContent = content;
        messageContent.appendChild(contentP);
        
        // 添加元数据（仅助手消息）
        if (type === 'assistant' && metadata.confidence) {
            const metaDiv = document.createElement('div');
            metaDiv.className = 'message-meta';
            metaDiv.innerHTML = `
                <small>
                    置信度: ${(metadata.confidence * 100).toFixed(1)}% | 
                    响应时间: ${metadata.responseTime?.toFixed(2)}s
                </small>
            `;
            messageContent.appendChild(metaDiv);
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    showTyping() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant-message typing-message';
        typingDiv.innerHTML = `
            <div class="assistant-avatar">🤖</div>
            <div class="message-content">
                <div class="loading"></div>
                <span>正在思考中...</span>
            </div>
        `;
        
        this.chatContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTyping() {
        const typingMessage = this.chatContainer.querySelector('.typing-message');
        if (typingMessage) {
            typingMessage.remove();
        }
    }
    
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        
        this.chatContainer.appendChild(errorDiv);
        this.scrollToBottom();
        
        // 3秒后自动移除错误消息
        setTimeout(() => {
            errorDiv.remove();
        }, 3000);
    }
    
    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }
    
    // 快捷问题处理
    askQuestion(question) {
        this.addMessage('user', question);
        this.sendQuestion(question);
    }
}

// 全局函数（保持向后兼容）
let app;

function toggleRecording() {
    if (app) {
        app.toggleRecording();
    }
}

function sendTextMessage() {
    if (app) {
        app.sendTextMessage();
    }
}

function askQuestion(question) {
    if (app) {
        app.askQuestion(question);
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', function() {
    console.log('📱 页面加载完成，初始化应用...');
    app = new SocialWiseApp();
    
    // 添加快捷问题按钮事件
    const quickButtons = document.querySelectorAll('.quick-question');
    quickButtons.forEach(button => {
        button.addEventListener('click', function() {
            const question = this.textContent;
            askQuestion(question);
        });
    });
    
    console.log('🎉 SocialWise 应用初始化完成！');
});

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SocialWiseApp };
}