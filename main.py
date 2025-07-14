from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

#Initialize FastAPI app

app = FastAPI()

# Pydantic model
class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    price: float = Field(..., gt=0)

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    price: Optional[float] = Field(None, gt=0)

class Item(ItemBase):
    id: int

class ItemBatchUpdate(BaseModel):
    item_ids: List[int]
    item_update: ItemUpdate

class OperationType(str, Enum):
    eq = "="
    gt = ">"
    lt = "<"
    gte = ">="
    lte = "<="
    in_ = "IN"

class Condition(BaseModel):
    key: str
    operation: OperationType
    value: Optional[object]

class ConditionalBatchUpdate(BaseModel):
    conditions: List[Condition]
    internal_operation: str = Field(..., pattern="^(AND|OR)$")
    item_update: ItemUpdate

# In-memory "database"
items_db: List[Item] = []
item_id_counter = 1

# POST create item
@app.post("/items", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    global item_id_counter
    new_item = Item(id=item_id_counter, **item.dict())
    items_db.append(new_item)
    item_id_counter += 1
    return new_item

# GET all items
@app.get("/items", response_model=List[Item])
def get_items():
    return items_db

# GET single item
@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    for item in items_db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

# PUT update item
@app.put("/items/{item_id}", response_model=Item)
def update_item(item_id: int, item_update: ItemUpdate):
    for idx, item in enumerate(items_db):
        if item.id == item_id:
            updated_data = item.dict()
            update_fields = item_update.dict(exclude_unset=True) # Exclude unset fields to allow partial updates
            updated_data.update(update_fields)
            updated_item = Item(**updated_data)
            items_db[idx] = updated_item
            return updated_item
    raise HTTPException(status_code=404, detail="Item not found")


# PUT batchupdate item
@app.put("/items_batch_update", response_model=List[Item])
def batch_update_items(items: ItemBatchUpdate):
    """ 
    Sample input for batch update:
    {
        "item_ids":[1,2]
        "item_update": {
            "name":"Updated Name",
            "description":"Updated Description"}   
    }
    """
    updated_items = []
    for item_id in items.item_ids:
        found = False
        for idx, item in enumerate(items_db):
            if item.id == item_id:
                updated_data = item.dict()
                update_fields = items.item_update.dict(exclude_unset=True)
                updated_data.update(update_fields)
                updated_item = Item(**updated_data)
                items_db[idx] = updated_item
                updated_items.append(updated_item)
                found = True
                break
        if not found: 
            raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
    return updated_items



# PUT conditional batch update
@app.put("/items_conditional_update", response_model=List[Item])
def conditional_update_items(payload: ConditionalBatchUpdate):
    """
    Sample payload:
    {
        "conditions": [
            {"key": "name", "operation": "=", "value": "Item 1"},
            {"key": "price", "operation": ">", "value": 10}
        ],
        "internal_operation": "AND",
        "item_update": {
            "description": "Updated description",
            "price": 99.99
        }
    }
    """
    matched_indices = []
    for idx, item in enumerate(items_db):
        results = [match_condition(item, cond) for cond in payload.conditions]
        if payload.internal_operation == "AND":
            matched = all(results)
        else:
            matched = any(results)
        if matched:
            matched_indices.append(idx)
    if not matched_indices:
        raise HTTPException(status_code=404, detail="No items matched the conditions")
    updated_items = []
    update_fields = payload.item_update.dict(exclude_unset=True)
    for idx in matched_indices:
        updated_data = items_db[idx].dict()
        updated_data.update(update_fields)
        updated_item = Item(**updated_data)
        items_db[idx] = updated_item
        updated_items.append(updated_item)
    return updated_items

# DELETE item
@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    for idx, item in enumerate(items_db):
        if item.id == item_id:
            items_db.pop(idx)
            return
    raise HTTPException(status_code=404, detail="Item not found")

def match_condition(item: Item, condition: Condition):
    item_value = getattr(item, condition.key, None)
    if item_value is None:
        return False
    op = condition.operation
    val = condition.value
    if op == OperationType.eq:
        return item_value == val
    elif op == OperationType.gt:
        return item_value > val
    elif op == OperationType.lt:
        return item_value < val
    elif op == OperationType.gte:
        return item_value >= val
    elif op == OperationType.lte:
        return item_value <= val
    elif op == OperationType.in_:
        return item_value in val if isinstance(val, list) else False
    return False
