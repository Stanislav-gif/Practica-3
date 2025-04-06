from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional

# Создание базы данных и модели
DATABASE_URL = "sqlite:///./energy_drinks.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class EnergyDrink(Base):
    __tablename__ = "energy_drinks"
    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String, index=True)
    name = Column(String)
    volume_ml = Column(Integer)  # Объем в миллилитрах
    price = Column(Integer)     # Цена в рублях
    stock = Column(Integer)     # Количество оставшихся единиц товара

Base.metadata.create_all(bind=engine)

# Модели Pydantic для валидации
class EnergyDrinkCreate(BaseModel):
    brand: str
    name: str
    volume_ml: int
    price: int
    stock: int

class EnergyDrinkUpdate(BaseModel):
    brand: Optional[str] = None
    name: Optional[str] = None
    volume_ml: Optional[int] = None
    price: Optional[int] = None
    stock: Optional[int] = None

class EnergyDrinkResponse(BaseModel):
    id: int
    brand: str
    name: str
    volume_ml: int
    price: int
    stock: int

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

@app.get("/energy-drinks/", response_model=List[EnergyDrinkResponse])
def read_energy_drinks(
    skip: int = 0,
    limit: int = 10,
    sort_by: Optional[str] = Query(None, description="Сортировка по полю (например, brand, price)"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки (asc/desc)"),
    filter_brand: Optional[str] = Query(None, description="Фильтр по бренду"),
    filter_volume: Optional[int] = Query(None, description="Фильтр по объему"),
    search: Optional[str] = Query(None, description="Поиск по бренду или названию"),
    db: Session = Depends(get_db)
):
    query = db.query(EnergyDrink)

    # Применение фильтров
    if filter_brand:
        query = query.filter(EnergyDrink.brand == filter_brand)
    if filter_volume:
        query = query.filter(EnergyDrink.volume_ml == filter_volume)
    if search:
        query = query.filter((EnergyDrink.brand.contains(search)) | (EnergyDrink.name.contains(search)))

    # Применение сортировки
    if sort_by:
        column = getattr(EnergyDrink, sort_by, None)
        if column is not None:
            if sort_order.lower() == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

    # Пагинация
    energy_drinks = query.offset(skip).limit(limit).all()
    return energy_drinks

@app.get("/energy-drinks/{drink_id}", response_model=EnergyDrinkResponse)
def read_energy_drink(drink_id: int, db: Session = Depends(get_db)):
    drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
    if drink is None:
        raise HTTPException(status_code=404, detail="Energy drink not found")
    return drink

@app.post("/energy-drinks/", response_model=EnergyDrinkResponse)
def create_energy_drink(drink: EnergyDrinkCreate, db: Session = Depends(get_db)):
    db_drink = EnergyDrink(**drink.dict())
    db.add(db_drink)
    db.commit()
    db.refresh(db_drink)
    return db_drink

@app.put("/energy-drinks/{drink_id}", response_model=EnergyDrinkResponse)
def update_energy_drink(drink_id: int, drink: EnergyDrinkUpdate, db: Session = Depends(get_db)):
    db_drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
    if db_drink is None:
        raise HTTPException(status_code=404, detail="Energy drink not found")
    
    for key, value in drink.dict(exclude_unset=True).items():
        setattr(db_drink, key, value)
    db.commit()
    db.refresh(db_drink)
    return db_drink

@app.delete("/energy-drinks/{drink_id}", status_code=204)
def delete_energy_drink(drink_id: int, db: Session = Depends(get_db)):
    db_drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
    if db_drink is None:
        raise HTTPException(status_code=404, detail="Energy drink not found")
    db.delete(db_drink)
    db.commit()
    return None

@app.post("/energy-drinks/{drink_id}/buy", response_model=EnergyDrinkResponse)
def buy_energy_drink(drink_id: int, quantity: int = 1, db: Session = Depends(get_db)):
    db_drink = db.query(EnergyDrink).filter(EnergyDrink.id == drink_id).first()
    if db_drink is None:
        raise HTTPException(status_code=404, detail="Energy drink not found")
    if db_drink.stock < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")
    
    db_drink.stock -= quantity
    db.commit()
    db.refresh(db_drink)
    return db_drink