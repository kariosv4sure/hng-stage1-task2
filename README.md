# HNG Stage 1 Task 2 - Profile API

REST API that aggregates demographic predictions from Genderize, Agify, and Nationalize APIs.

## 🚀 Live URL
`https://hng-stage1-task2.railway.app`

## 📚 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profiles` | Create profile from name |
| GET | `/api/profiles` | List all profiles (filter: gender, country_id, age_group) |
| GET | `/api/profiles/{id}` | Get single profile |
| DELETE | `/api/profiles/{id}` | Delete profile |

## 🛠 Local Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
