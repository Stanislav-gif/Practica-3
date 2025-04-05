from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional

# Создание базы данных и модели
DATABASE_URL = "sqlite:///./cars.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    make = Column(String, index=True)
    model = Column(String)
    year = Column(Integer)
    color = Column(String)
    views = Column(Integer, default=0)  # Новая колонка для отслеживания просмотров(фича)

Base.metadata.create_all(bind=engine)

# Модели Pydantic для валидации
class CarCreate(BaseModel):
    make: str
    model: str
    year: int
    color: str

class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None

class CarResponse(BaseModel):
    id: int
    make: str
    model: str
    year: int
    color: str
    views: int  # Добавляем поле для просмотров

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

@app.get("/cars/", response_model=List[CarResponse])
def read_cars(
    skip: int = 0,
    limit: int = 10,
    sort_by: Optional[str] = Query(None, description="Сортировка по полю (например, make, year)"),
    sort_order: Optional[str] = Query("asc", description="Порядок сортировки (asc/desc)"),
    filter_make: Optional[str] = Query(None, description="Фильтр по марке"),
    filter_year: Optional[int] = Query(None, description="Фильтр по году"),
    search: Optional[str] = Query(None, description="Поиск по марке или модели"),
    db: Session = Depends(get_db)
):
    query = db.query(Car)

    # Применение фильтров
    if filter_make:
        query = query.filter(Car.make == filter_make)
    if filter_year:
        query = query.filter(Car.year == filter_year)
    if search:
        query = query.filter((Car.make.contains(search)) | (Car.model.contains(search)))

    # Применение сортировки
    if sort_by:
        column = getattr(Car, sort_by, None)
        if column is not None:
            if sort_order.lower() == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

    # Пагинация
    cars = query.offset(skip).limit(limit).all()
    return cars

@app.get("/cars/{car_id}", response_model=CarResponse)
def read_car(car_id: int, db: Session = Depends(get_db)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Увеличиваем счетчик просмотров
    car.views += 1
    db.commit()
    db.refresh(car)
    return car

@app.post("/cars/", response_model=CarResponse)
def create_car(car: CarCreate, db: Session = Depends(get_db)):
    db_car = Car(**car.dict(), views=0)  # Инициализация с нулевым количеством просмотров
    db.add(db_car)
    db.commit()
    db.refresh(db_car)
    return db_car

@app.put("/cars/{car_id}", response_model=CarResponse)
def update_car(car_id: int, car: CarUpdate, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    for key, value in car.dict(exclude_unset=True).items():
        setattr(db_car, key, value)
    db.commit()
    db.refresh(db_car)
    return db_car

@app.delete("/cars/{car_id}", status_code=204)
def delete_car(car_id: int, db: Session = Depends(get_db)):
    db_car = db.query(Car).filter(Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    db.delete(db_car)
    db.commit()
    return None