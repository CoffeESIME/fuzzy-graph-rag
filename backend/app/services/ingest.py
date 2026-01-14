"""
Ingest service for orchestrating file uploads and metadata creation.
"""

from typing import List, Tuple, Dict, Set
from fastapi import UploadFile, HTTPException
from sqlmodel import Session
import hashlib
import mimetypes
import uuid
import json
from datetime import datetime

from app.models import Asset, VectorStatus, JobStatus, PrivacyLevel
from app.schemas import UploadGroup, ProcessingOperation
from app.schemas.sidecar import SidecarMetadata, PrivacyConfig, WorkflowState, DataLayers, IntermediateResults
from shared.clients import get_minio_client


class IngestService:
    """
    Service for orchestrating the ingestion pipeline.
    
    Responsibilities:
    1. Validate upload maps
    2. Upload files to MinIO
    3. Generate sidecar JSON metadata
    4. Create Asset records in PostgreSQL
    5. Create VectorStatus records in ON_HOLD state
    """
    
    BUCKET_NAME = "rag-dataset"
    
    def __init__(self, session: Session):
        self.session = session
        self.s3 = get_minio_client()
    
    async def process_upload(
        self,
        files: List[UploadFile],
        upload_map: List[UploadGroup]
    ) -> Dict:
        """
        Main entry point for processing file uploads.
        
        Args:
            files: List of uploaded files
            upload_map: List of UploadGroup defining how to process files
            
        Returns:
            Dict with created assets and metadata
        """
        # Validate upload map
        self._validate_upload_map(files, upload_map)
        
        created_assets = []
        total_files_processed = 0
        
        # Process each group
        for group in upload_map:
            if group.operation == ProcessingOperation.STANDARD:
                # Process each file individually
                for file_idx in group.file_indices:
                    asset = await self._handle_standard(
                        files[file_idx],
                        group
                    )
                    created_assets.append(asset)
                    total_files_processed += 1
            
            elif group.operation == ProcessingOperation.MERGE_OCR:
                # Process multiple files as one logical asset
                grouped_files = [files[idx] for idx in group.file_indices]
                asset = await self._handle_merge_ocr(
                    grouped_files,
                    group
                )
                created_assets.append(asset)
                total_files_processed += len(group.file_indices)
        
        return {
            "assets_created": created_assets,
            "total_files_processed": total_files_processed
        }
    
    def _validate_upload_map(
        self,
        files: List[UploadFile],
        upload_map: List[UploadGroup]
    ):
        """
        Validate that upload map indices are valid and non-duplicate.
        
        Raises:
            HTTPException: If validation fails
        """
        num_files = len(files)
        seen_indices: Set[int] = set()
        
        for group in upload_map:
            for idx in group.file_indices:
                # Check bounds
                if idx >= num_files:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File index {idx} is out of range (only {num_files} files uploaded)"
                    )
                
                # Check duplicates
                if idx in seen_indices:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File index {idx} appears in multiple groups"
                    )
                
                seen_indices.add(idx)
    
    async def _handle_standard(
        self,
        file: UploadFile,
        group: UploadGroup
    ) -> Asset:
        """
        Handle STANDARD operation: 1 file = 1 asset.
        
        Args:
            file: The uploaded file
            group: Processing instructions
            
        Returns:
            Created Asset instance
        """
        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset for potential re-reads
        
        # Calculate hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Determine MIME type
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        
        # Determine storage path based on mime type
        if mime_type.startswith("image/"):
            category = "images"
        elif mime_type.startswith("video/"):
            category = "videos"
        elif mime_type.startswith("audio/"):
            category = "audio"
        else:
            category = "documents"
        
        # Upload to MinIO
        minio_path = f"raw/{category}/{file_hash[:8]}_{file.filename}"
        self.s3.put_object(
            Bucket=self.BUCKET_NAME,
            Key=minio_path,
            Body=content,
            ContentType=mime_type
        )
        
        # Generate sidecar with new structure
        sidecar_path = f"master_records/sidecars/{file_hash}.json"
        sidecar_data = SidecarMetadata(
            file_hash=file_hash,
            original_filename=file.filename,
            mime_type=mime_type,
            size_bytes=len(content),
            upload_timestamp=datetime.utcnow(),
            operation=group.operation.value,
            user_notes=group.user_notes,
            discard_original=group.discard_original,
            vector_types=[vt.value for vt in group.vector_types],
            is_merged=False,
            source_files=[file.filename],
            privacy_config=PrivacyConfig(
                level=group.privacy_level,
                locked=False
            ),
            workflow_state=WorkflowState(
                steps_completed=["upload"],
                current_status=JobStatus.ON_HOLD
            ),
            data_layers=DataLayers()
        )
        
        self.s3.put_object(
            Bucket=self.BUCKET_NAME,
            Key=sidecar_path,
            Body=sidecar_data.model_dump_json(indent=2).encode('utf-8'),
            ContentType="application/json"
        )
        
        # Create Asset record
        asset = Asset(
            filename=file.filename,
            minio_path=minio_path,
            mime_type=mime_type,
            size_bytes=len(content),
            file_hash=file_hash,
            is_merged=False,
            original_deleted=False,  # Will be updated by worker if discard_original=True
            privacy_level=group.privacy_level,
            sidecar_path=sidecar_path
        )
        
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        
        # Create VectorStatus records
        self._create_vector_statuses(asset, group.vector_types)
        
        return asset
    
    async def _handle_merge_ocr(
        self,
        files: List[UploadFile],
        group: UploadGroup
    ) -> Asset:
        """
        Handle MERGE_OCR operation: N files = 1 logical text asset.
        
        Args:
            files: List of files to merge
            group: Processing instructions
            
        Returns:
            Created Asset instance representing the merged entity
        """
        batch_uuid = str(uuid.uuid4())
        temp_folder = f"raw/temp/{batch_uuid}/"
        
        # Upload individual files to temp folder
        uploaded_files = []
        total_size = 0
        
        for file in files:
            content = await file.read()
            await file.seek(0)
            
            file_hash = hashlib.sha256(content).hexdigest()
            temp_path = f"{temp_folder}{file_hash[:8]}_{file.filename}"
            
            self.s3.put_object(
                Bucket=self.BUCKET_NAME,
                Key=temp_path,
                Body=content,
                ContentType=file.content_type or "application/octet-stream"
            )
            
            uploaded_files.append({
                "filename": file.filename,
                "path": temp_path,
                "hash": file_hash,
                "size": len(content)
            })
            total_size += len(content)
        
        # Create a synthetic hash for the merged asset
        combined_hashes = "".join([f["hash"] for f in uploaded_files])
        merged_hash = hashlib.sha256(combined_hashes.encode()).hexdigest()
        
        # Generate filename for merged asset
        merged_filename = f"merged_ocr_{batch_uuid[:8]}.txt"
        
        # Create sidecar for merged asset
        sidecar_path = f"master_records/sidecars/{merged_hash}.json"
        sidecar_data = SidecarMetadata(
            file_hash=merged_hash,
            original_filename=merged_filename,
            mime_type="text/plain",  # Merged OCR will be text
            size_bytes=total_size,
            upload_timestamp=datetime.utcnow(),
            operation=group.operation.value,
            user_notes=group.user_notes,
            discard_original=group.discard_original,
            vector_types=[vt.value for vt in group.vector_types],
            is_merged=True,
            source_files=uploaded_files,
            batch_uuid=batch_uuid,
            privacy_config=PrivacyConfig(
                level=group.privacy_level,
                locked=False
            ),
            workflow_state=WorkflowState(
                steps_completed=["upload", "file_grouping"],
                current_status=JobStatus.ON_HOLD
            ),
            data_layers=DataLayers()
        )
        
        self.s3.put_object(
            Bucket=self.BUCKET_NAME,
            Key=sidecar_path,
            Body=sidecar_data.model_dump_json(indent=2).encode('utf-8'),
            ContentType="application/json"
        )
        
        # Create Asset record for the logical merged entity
        asset = Asset(
            filename=merged_filename,
            minio_path=temp_folder,  # Points to the temp folder containing source files
            mime_type="text/plain",
            size_bytes=total_size,
            file_hash=merged_hash,
            is_merged=True,
            original_deleted=False,  # Will be updated by worker after OCR
            privacy_level=group.privacy_level,
            sidecar_path=sidecar_path
        )
        
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        
        # Create VectorStatus records
        self._create_vector_statuses(asset, group.vector_types)
        
        return asset
    
    def _create_vector_statuses(
        self,
        asset: Asset,
        vector_types: List
    ):
        """
        Create VectorStatus records for each vector type in ON_HOLD state.
        
        Args:
            asset: The asset to create statuses for
            vector_types: List of VectorType enums
        """
        for vector_type in vector_types:
            status = VectorStatus(
                asset_id=asset.id,
                vector_type=vector_type,
                status=JobStatus.ON_HOLD
            )
            self.session.add(status)
        
        self.session.commit()
