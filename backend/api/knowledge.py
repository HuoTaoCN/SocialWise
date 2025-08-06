"""
知识库管理API
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from backend.models.schemas import FAQItem, TrustedQA, DocumentInfo, FileUploadResponse
from backend.services.knowledge_service import KnowledgeService
from backend.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化知识库服务
knowledge_service = KnowledgeService()

# FAQ管理
@router.get("/faq", response_model=List[FAQItem])
async def get_faq_list(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取FAQ列表"""
    try:
        faqs = await knowledge_service.get_faq_list(
            category=category,
            keyword=keyword,
            limit=limit,
            offset=offset,
            db=db
        )
        return faqs
    except Exception as e:
        logger.error(f"获取FAQ列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/faq", response_model=FAQItem)
async def create_faq(
    faq: FAQItem,
    db: AsyncSession = Depends(get_db)
):
    """创建FAQ"""
    try:
        new_faq = await knowledge_service.create_faq(faq, db)
        return new_faq
    except Exception as e:
        logger.error(f"创建FAQ失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/faq/{faq_id}", response_model=FAQItem)
async def update_faq(
    faq_id: int,
    faq: FAQItem,
    db: AsyncSession = Depends(get_db)
):
    """更新FAQ"""
    try:
        updated_faq = await knowledge_service.update_faq(faq_id, faq, db)
        if not updated_faq:
            raise HTTPException(status_code=404, detail="FAQ不存在")
        return updated_faq
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新FAQ失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/faq/{faq_id}")
async def delete_faq(
    faq_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除FAQ"""
    try:
        success = await knowledge_service.delete_faq(faq_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="FAQ不存在")
        return {"message": "FAQ删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除FAQ失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 可信QA对管理
@router.get("/trusted-qa", response_model=List[TrustedQA])
async def get_trusted_qa_list(
    verified_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取可信QA对列表"""
    try:
        qa_pairs = await knowledge_service.get_trusted_qa_list(
            verified_only=verified_only,
            limit=limit,
            offset=offset,
            db=db
        )
        return qa_pairs
    except Exception as e:
        logger.error(f"获取可信QA对列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trusted-qa", response_model=TrustedQA)
async def create_trusted_qa(
    qa: TrustedQA,
    db: AsyncSession = Depends(get_db)
):
    """创建可信QA对"""
    try:
        new_qa = await knowledge_service.create_trusted_qa(qa, db)
        return new_qa
    except Exception as e:
        logger.error(f"创建可信QA对失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/trusted-qa/{qa_id}/verify")
async def verify_trusted_qa(
    qa_id: int,
    verified_by: str,
    db: AsyncSession = Depends(get_db)
):
    """验证可信QA对"""
    try:
        success = await knowledge_service.verify_trusted_qa(qa_id, verified_by, db)
        if not success:
            raise HTTPException(status_code=404, detail="QA对不存在")
        return {"message": "QA对验证成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证QA对失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 文档管理
@router.post("/documents/upload", response_model=FileUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """上传文档"""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        # 检查文件类型
        allowed_types = ['.pdf', '.txt', '.docx', '.md']
        file_ext = '.' + file.filename.split('.')[-1].lower()
        if file_ext not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型，支持的类型: {', '.join(allowed_types)}"
            )
        
        result = await knowledge_service.upload_document(file, db)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents", response_model=List[DocumentInfo])
async def get_document_list(
    processed_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取文档列表"""
    try:
        documents = await knowledge_service.get_document_list(
            processed_only=processed_only,
            limit=limit,
            offset=offset,
            db=db
        )
        return documents
    except Exception as e:
        logger.error(f"获取文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/{doc_id}/process")
async def process_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db)
):
    """处理文档（提取文本并向量化）"""
    try:
        success = await knowledge_service.process_document(doc_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {"message": "文档处理已开始"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除文档"""
    try:
        success = await knowledge_service.delete_document(doc_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {"message": "文档删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 向量搜索
@router.post("/search")
async def vector_search(
    query: str,
    top_k: int = 5,
    source_types: Optional[List[str]] = None
):
    """向量搜索"""
    try:
        if not query.strip():
            raise HTTPException(status_code=400, detail="查询内容不能为空")
        
        results = await knowledge_service.vector_search(
            query=query,
            top_k=top_k,
            source_types=source_types
        )
        return {"results": results}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))