from pydantic import BaseModel
from beanie import Document, PydanticObjectId
from typing import Any, List, Optional, Union

class Database:
    def __init__(self, model):
        self.model = model

    async def create(self, document: Document) -> None:
        await document.create()
        return

    async def get(self, id: PydanticObjectId) -> Union[Document, bool]:
        doc = await self.model.get(id)
        if doc:
            return doc
        return False

    async def get_all(self) -> List[Any]:
        docs = await self.model.find_all().to_list()
        return docs

    async def update(self, id: PydanticObjectId, body: BaseModel) -> Any:
        doc_id = id
        des_body = body.dict()
        des_body = {k: v for k, v in des_body.items() if v is not None}
        update_query = {"$set": {field: value for field, value in des_body.items()}}
        doc = await self.get(doc_id)
        if not doc:
            return False
        await doc.update(update_query)
        return doc

    async def delete(self, id: PydanticObjectId) -> bool:
        doc = await self.get(id)
        if not doc:
            return False
        await doc.delete()
        return True
