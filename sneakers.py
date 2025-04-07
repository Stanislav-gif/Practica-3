from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional

# Создание базы данных и модели
DATABASE_URL = "sqlite:///./sneakers.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Sneaker(Base):
    __tablename__ = "sneakers"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String, index=True)  
    model = Column(String)              
    price = Column(Integer)             
    rating = Column(Float, default=0.0) # Рейтинг кроссовок (от 0 до 5)

Base.metadata.create_all(bind=engine)

# Модели Pydantic для валидации
class SneakerCreate(BaseModel):
    brand: str
    model: str
    price: int

class SneakerUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    price: Optional[int] = None
    rating: Optional[float] = None

class SneakerResponse(BaseModel):
    id: int
    brand: str
    model: str
    price: int
    rating: float

    class Config:
        orm_mode = True

app = FastAPI()

# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/sneakers/", response_model=List[SneakerResponse])
def read_sneakers(
    skip: int = 0,
    limit: int = 10,
    sort_by: Optional[str] = Query(None, description="Сортировка по полю (например, brand, price, rating)"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки (asc/desc)"),
    filter_brand: Optional[str] = Query(None, description="Фильтр по бренду"),
    filter_price_min: Optional[int] = Query(None, description="Минимальная цена"),
    filter_price_max: Optional[int] = Query(None, description="Максимальная цена"),
    search: Optional[str] = Query(None, description="Поиск по бренду или модели"),
    db: Session = Depends(get_db)
):
    query = db.query(Sneaker)

    # Применение фильтров
    if filter_brand:
        query = query.filter(Sneaker.brand == filter_brand)
    if filter_price_min:
        query = query.filter(Sneaker.price >= filter_price_min)
    if filter_price_max:
        query = query.filter(Sneaker.price <= filter_price_max)
    if search:
        query = query.filter((Sneaker.brand.contains(search)) | (Sneaker.model.contains(search)))

    # Применение сортировки
    if sort_by:
        column = getattr(Sneaker, sort_by, None)
        if column is not None:
            if sort_order.lower() == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

    # Пагинация
    sneakers = query.offset(skip).limit(limit).all()
    return sneakers

@app.get("/sneakers/{sneaker_id}", response_model=SneakerResponse)
def read_sneaker(sneaker_id: int, db: Session = Depends(get_db)):
    sneaker = db.query(Sneaker).filter(Sneaker.id == sneaker_id).first()
    if sneaker is None:
        raise HTTPException(status_code=404, detail="Sneaker not found")
    return sneaker

@app.post("/sneakers/", response_model=SneakerResponse)
def create_sneaker(sneaker: SneakerCreate, db: Session = Depends(get_db)):
    db_sneaker = Sneaker(**sneaker.dict(), rating=0.0)
    db.add(db_sneaker)
    db.commit()
    db.refresh(db_sneaker)
    return db_sneaker

@app.put("/sneakers/{sneaker_id}", response_model=SneakerResponse)
def update_sneaker(sneaker_id: int, sneaker: SneakerUpdate, db: Session = Depends(get_db)):
    db_sneaker = db.query(Sneaker).filter(Sneaker.id == sneaker_id).first()
    if db_sneaker is None:
        raise HTTPException(status_code=404, detail="Sneaker not found")
    
    for key, value in sneaker.dict(exclude_unset=True).items():
        setattr(db_sneaker, key, value)
    db.commit()
    db.refresh(db_sneaker)
    return db_sneaker

@app.delete("/sneakers/{sneaker_id}", status_code=204)
def delete_sneaker(sneaker_id: int, db: Session = Depends(get_db)):
    db_sneaker = db.query(Sneaker).filter(Sneaker.id == sneaker_id).first()
    if db_sneaker is None:
        raise HTTPException(status_code=404, detail="Sneaker not found")
    db.delete(db_sneaker)
    db.commit()
    return None

@app.post("/sneakers/{sneaker_id}/rate", response_model=SneakerResponse)
def rate_sneaker(
    sneaker_id: int,
    rating: float = Query(..., ge=0, le=5, description="Новый рейтинг (от 0 до 5)"),
    db: Session = Depends(get_db)
):
    db_sneaker = db.query(Sneaker).filter(Sneaker.id == sneaker_id).first()
    if db_sneaker is None:
        raise HTTPException(status_code=404, detail="Sneaker not found")
    
    db_sneaker.rating = rating
    db.commit()
    db.refresh(db_sneaker)
    return db_sneaker