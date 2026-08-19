# -*- coding: utf-8 -*-
"""
MongoDB Atlas 데이터 전체를 JSON으로 백업하는 스크립트.
GitHub Actions에서 매일 자정(KST)에 자동 실행된다. (.github/workflows/backup-mongo.yml 참고)

수동 실행:
    MONGO_URI="mongodb+srv://..." python scripts/backup_mongo.py

환경변수:
    MONGO_URI      - MongoDB 연결 문자열 (필수)
    MONGO_DB_NAME  - DB 이름 (기본값: hellini_routine)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

COLLECTIONS = ["users", "logs", "inquiries"]

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
LATEST_DIR = BACKUP_DIR / "latest"


def _default(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"직렬화할 수 없는 타입입니다: {type(obj)}")


def main():
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI 환경변수가 없습니다. (GitHub Actions Secrets 또는 로컬 환경변수 확인)", file=sys.stderr)
        sys.exit(1)
    db_name = os.environ.get("MONGO_DB_NAME", "hellini_routine")

    client = MongoClient(uri)
    db = client[db_name]

    LATEST_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}
    for name in COLLECTIONS:
        docs = list(db[name].find())
        out_path = LATEST_DIR / f"{name}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2, default=_default)
        summary[name] = len(docs)

    meta = {
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "db_name": db_name,
        "counts": summary,
    }
    with (LATEST_DIR / "_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("백업 완료:", summary)


if __name__ == "__main__":
    main()
