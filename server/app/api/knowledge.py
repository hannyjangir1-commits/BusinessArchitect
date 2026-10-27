from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import Project, ProjectKnowledgeItem, KnowledgeLink
from app.schemas.knowledge import (
    KnowledgeItemCreate, KnowledgeItemUpdate, KnowledgeItemResponse,
    KnowledgeLinkCreate, KnowledgeLinkResponse
)
from app.api.deps import get_user_project, verify_csrf

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["Shared Knowledge Model"])

def _format_knowledge_item(
    item: ProjectKnowledgeItem,
    db: Optional[Session] = None,
    out_links: Optional[List[KnowledgeLink]] = None,
    in_links: Optional[List[KnowledgeLink]] = None
) -> KnowledgeItemResponse:
    if out_links is None and db is not None:
        out_links = db.query(KnowledgeLink).filter(KnowledgeLink.source_id == item.id).all()
    if in_links is None and db is not None:
        in_links = db.query(KnowledgeLink).filter(KnowledgeLink.target_id == item.id).all()

    out_links = out_links or []
    in_links = in_links or []

    return KnowledgeItemResponse(
        id=item.id,
        project_id=item.project_id,
        item_type=item.item_type,
        title=item.title,
        content=item.content,
        status=item.status,
        epistemic_status=item.epistemic_status,
        source_reference=item.source_reference,
        linked_module=item.linked_module,
        metadata_json=item.metadata_json or {},
        created_at=item.created_at,
        updated_at=item.updated_at,
        outgoing_links=[KnowledgeLinkResponse.model_validate(l) for l in out_links],
        incoming_links=[KnowledgeLinkResponse.model_validate(l) for l in in_links]
    )

@router.get("", response_model=List[KnowledgeItemResponse])
def list_knowledge_items(
    item_type: Optional[str] = Query(None, description="Filter by item_type (fact, assumption, evidence, decision, experiment, open_question)"),
    epistemic_status: Optional[str] = Query(None, description="Filter by epistemic_status"),
    linked_module: Optional[str] = Query(None, description="Filter by linked module"),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    query = db.query(ProjectKnowledgeItem).filter(ProjectKnowledgeItem.project_id == project.id)
    if item_type:
        query = query.filter(ProjectKnowledgeItem.item_type == item_type)
    if epistemic_status:
        query = query.filter(ProjectKnowledgeItem.epistemic_status == epistemic_status)
    if linked_module:
        query = query.filter(ProjectKnowledgeItem.linked_module == linked_module)
        
    items = query.order_by(ProjectKnowledgeItem.created_at.desc()).all()
    if not items:
        return []

    item_ids = [i.id for i in items]
    links = db.query(KnowledgeLink).filter(
        (KnowledgeLink.source_id.in_(item_ids)) | (KnowledgeLink.target_id.in_(item_ids))
    ).all()

    out_by_source: dict[str, list[KnowledgeLink]] = {}
    in_by_target: dict[str, list[KnowledgeLink]] = {}
    for link in links:
        out_by_source.setdefault(link.source_id, []).append(link)
        in_by_target.setdefault(link.target_id, []).append(link)

    return [
        _format_knowledge_item(
            i,
            out_links=out_by_source.get(i.id, []),
            in_links=in_by_target.get(i.id, [])
        )
        for i in items
    ]

@router.post("", response_model=KnowledgeItemResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_knowledge_item(
    req: KnowledgeItemCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    item = ProjectKnowledgeItem(
        project_id=project.id,
        item_type=req.item_type,
        title=req.title,
        content=req.content,
        status=req.status,
        epistemic_status=req.epistemic_status,
        source_reference=req.source_reference,
        linked_module=req.linked_module,
        metadata_json=req.metadata_json
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _format_knowledge_item(item, db=db)

@router.get("/{item_id}", response_model=KnowledgeItemResponse)
def get_knowledge_item(
    item_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    item = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.id == item_id,
        ProjectKnowledgeItem.project_id == project.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
    return _format_knowledge_item(item, db=db)

@router.put("/{item_id}", response_model=KnowledgeItemResponse, dependencies=[Depends(verify_csrf)])
def update_knowledge_item(
    item_id: str,
    req: KnowledgeItemUpdate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    item = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.id == item_id,
        ProjectKnowledgeItem.project_id == project.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
        
    if req.title is not None:
        item.title = req.title
    if req.content is not None:
        item.content = req.content
    if req.status is not None:
        item.status = req.status
    if req.epistemic_status is not None:
        item.epistemic_status = req.epistemic_status
    if req.source_reference is not None:
        item.source_reference = req.source_reference
    if req.linked_module is not None:
        item.linked_module = req.linked_module
    if req.metadata_json is not None:
        item.metadata_json = req.metadata_json
        
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _format_knowledge_item(item, db=db)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_csrf)])
def delete_knowledge_item(
    item_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    item = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.id == item_id,
        ProjectKnowledgeItem.project_id == project.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found.")
    db.delete(item)
    db.commit()
    return None

@router.post("/links", response_model=KnowledgeLinkResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
def create_knowledge_link(
    req: KnowledgeLinkCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    source = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.id == req.source_id,
        ProjectKnowledgeItem.project_id == project.id
    ).first()
    target = db.query(ProjectKnowledgeItem).filter(
        ProjectKnowledgeItem.id == req.target_id,
        ProjectKnowledgeItem.project_id == project.id
    ).first()
    
    if not source or not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source or target knowledge item not found in project.")
    if source.id == target.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot link knowledge item to itself.")

    # Idempotently return existing link if identical link already exists
    existing_link = db.query(KnowledgeLink).filter(
        KnowledgeLink.project_id == project.id,
        KnowledgeLink.source_id == source.id,
        KnowledgeLink.target_id == target.id,
        KnowledgeLink.relationship == req.relationship
    ).first()
    if existing_link:
        return KnowledgeLinkResponse.model_validate(existing_link)
        
    link = KnowledgeLink(
        project_id=project.id,
        source_id=source.id,
        target_id=target.id,
        relationship=req.relationship
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return KnowledgeLinkResponse.model_validate(link)

@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_csrf)])
def delete_knowledge_link(
    link_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    link = db.query(KnowledgeLink).filter(
        KnowledgeLink.id == link_id,
        KnowledgeLink.project_id == project.id
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge link not found.")
    db.delete(link)
    db.commit()
    return None
