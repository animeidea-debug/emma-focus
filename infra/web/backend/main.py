from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI()

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AVATAR_FILE = "/app/data/avatar.txt"

# 确保 data 目录存在
os.makedirs("/app/data", exist_ok=True)

class AvatarData(BaseModel):
    avatar: str  # data:image/jpeg;base64,... 或 emoji 字符串

@app.get("/")
def read_root():
    return {"status": "site-backend is running"}

@app.post("/api/avatar/save")
async def save_avatar(data: AvatarData):
    try:
        with open(AVATAR_FILE, "w") as f:
            f.write(data.avatar)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/avatar/load")
async def load_avatar():
    try:
        if os.path.exists(AVATAR_FILE):
            with open(AVATAR_FILE, "r") as f:
                avatar = f.read()
            return {"status": "ok", "avatar": avatar}
        return {"status": "ok", "avatar": ""}
    except Exception as e:
        return {"status": "error", "message": str(e)}