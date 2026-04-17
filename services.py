import asyncio
from typing import Dict, Tuple, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from models import ProfileModel, generate_uuid7, get_age_group, utc_now


class ExternalAPIService:
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
    
    async def fetch_all(self, name: str) -> Dict:
        urls = {
            "genderize": f"https://api.genderize.io?name={name}",
            "agify": f"https://api.agify.io?name={name}",
            "nationalize": f"https://api.nationalize.io?name={name}"
        }
        
        try:
            async with asyncio.timeout(10.0):
                gender_resp, age_resp, nation_resp = await asyncio.gather(
                    self.client.get(urls["genderize"]),
                    self.client.get(urls["agify"]),
                    self.client.get(urls["nationalize"])
                )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "External API request timeout"}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "External API error"}
            )
        
        gender_data = self._validate_genderize(gender_resp)
        age_data = self._validate_agify(age_resp)
        nation_data = self._validate_nationalize(nation_resp)
        
        top_country = max(nation_data["country"], key=lambda x: x.get("probability", 0))
        
        return {
            "gender": gender_data["gender"],
            "gender_probability": gender_data["probability"],
            "sample_size": gender_data["count"],
            "age": age_data["age"],
            "age_group": get_age_group(age_data["age"]),
            "country_id": top_country.get("country_id", "UNKNOWN"),
            "country_probability": top_country.get("probability", 0.0)
        }
    
    def _validate_genderize(self, response: httpx.Response) -> Dict:
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Genderize returned an invalid response"}
            )
        data = response.json()
        if data.get("gender") is None or data.get("count", 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Genderize returned an invalid response"}
            )
        return data
    
    def _validate_agify(self, response: httpx.Response) -> Dict:
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Agify returned an invalid response"}
            )
        data = response.json()
        if data.get("age") is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Agify returned an invalid response"}
            )
        return data
    
    def _validate_nationalize(self, response: httpx.Response) -> Dict:
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Nationalize returned an invalid response"}
            )
        data = response.json()
        countries = data.get("country", [])
        if not countries:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"status": "error", "message": "Nationalize returned an invalid response"}
            )
        return data


class ProfileService:
    
    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[ProfileModel]:
        return db.query(ProfileModel).filter(ProfileModel.name == name).first()
    
    @staticmethod
    def get_by_id(db: Session, profile_id: str) -> Optional[ProfileModel]:
        return db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
    
    @staticmethod
    def get_all_filtered(
        db: Session,
        gender: Optional[str] = None,
        country_id: Optional[str] = None,
        age_group: Optional[str] = None
    ) -> list[ProfileModel]:
        query = db.query(ProfileModel)
        
        if gender:
            query = query.filter(func.lower(ProfileModel.gender) == gender.lower())
        if country_id:
            query = query.filter(func.lower(ProfileModel.country_id) == country_id.lower())
        if age_group:
            query = query.filter(func.lower(ProfileModel.age_group) == age_group.lower())
        
        return query.all()
    
    @staticmethod
    def create(db: Session, profile_data: Dict) -> Tuple[ProfileModel, bool]:
        try:
            new_profile = ProfileModel(
                id=generate_uuid7(),
                name=profile_data["name"],
                gender=profile_data["gender"],
                gender_probability=profile_data["gender_probability"],
                sample_size=profile_data["sample_size"],
                age=profile_data["age"],
                age_group=profile_data["age_group"],
                country_id=profile_data["country_id"],
                country_probability=profile_data["country_probability"],
                created_at=utc_now()
            )
            
            db.add(new_profile)
            db.commit()
            db.refresh(new_profile)
            return new_profile, False
            
        except IntegrityError:
            db.rollback()
            existing = ProfileService.get_by_name(db, profile_data["name"])
            return existing, True
    
    @staticmethod
    def delete(db: Session, profile: ProfileModel) -> None:
        db.delete(profile)
        db.commit()
