# -*- coding: utf-8 -*-
"""
backups/latest/ 안의 JSON 백업을 MongoDB(Atlas)에 복원하는 스크립트.
클러스터를 새로 만들었거나 데이터가 유실됐을 때, 이 스크립트로 되살린다.

사용법:
    MONGO_URI="mongodb+srv://..." python scripts/restore_mongo.py

옵션:
    --force   대상 컬렉션에 이미 데이터가 있어도 지우고 덮어쓰기
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

COLLECTIONS = ["users", "logs", "inquiries"]
LATEST_DIR = Path(__file__).resolve().parent.parent / "backups" / "latest"


def _object_hook(d):
    if "_id" in d and isinstance(d["_id"], str):
        try:
            d["_id"] = ObjectId(d["_id"])
        except Exception:
            pass
    for key in ("created_at", "updated_at", "last_seen"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = datetime.fromisoformat(d[key])
            except Exception:
                pass
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="대상 컬렉션에 데이터가 있어도 지우고 덮어쓰기")
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)
    db_name = os.environ.get("MONGO_DB_NAME", "hellini_routine")

    client = MongoClient(uri)
    db = client[db_name]

    for name in COLLECTIONS:
        path = LATEST_DIR / f"{name}.json"
        if not path.exists():
            print(f"백업 파일 없음, 건너뜀: {path}")
            continue
        with path.open("r", encoding="utf-8") as f:
            docs = json.load(f, object_hook=_object_hook)
        if not docs:
            print(f"[{name}] 백업 데이터 0건, 건너뜀")
            continue

        existing = db[name].count_documents({})
        if existing > 0 and not args.force:
            print(f"[{name}] 이미 {existing}개 문서가 있어 건너뜀 (덮어쓰려면 --force)")
            continue
        if existing > 0 and args.force:
            db[name].delete_many({})

        db[name].insert_many(docs)
        print(f"[{name}] {len(docs)}개 문서 복원 완료")

    print("\n복원 후 utils/db.py의 init_indexes()를 한 번 호출하거나,")
    print("앱을 재배포해서 인덱스(unique 등)가 다시 생성되게 해주세요.")


if __name__ == "__main__":
    main()
