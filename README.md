# 헬린이 루틴 (Streamlit)

기존 로컬 저장(localStorage) HTML 앱을 로그인 + 공용 랭킹 + 문의 게시판이 있는
멀티유저 Streamlit 앱으로 재구성한 버전입니다.

## 기능
- 회원가입/로그인 (아이디·비밀번호·닉네임, 전부 중복 불가)
- 오늘의 루틴 기록 (DAY1~4, 세트별 무게/횟수 입력, 메모)
- 마이페이지: 운동별 개인 최고기록(PR) + 날짜별 기록 히스토리 (삭제 가능)
- 랭킹
  - 👑 전체 종목 1위: 25개 운동 각각의 현재 챔피언(닉네임/무게/횟수)을 한 번에 확인
  - 📋 종목별 TOP 20: 운동 하나를 골라 순위표(최고 무게, 동률 시 최고 횟수)로 확인
- 문의하기: 운동 추가 요청 / 기능 개선 / 버그 신고 / 기타, 전체 공개 게시판 + 내 문의만 보기
- 실시간 현황: 사이드바에 총 가입자 수 / 현재 접속자 수(최근 5분 내 활동 기준) 상시 표시
- 관리자 페이지 (`ADMIN_USERNAMES`로 지정한 계정만 접근 가능)
  - 대시보드: 총 가입자·현재 접속자·총 기록 수·미처리 문의 수, 지금 접속 중인 사람 목록, 종목별 챔피언 요약
  - 회원 관리: 전체 회원 검색/조회, 계정 삭제(기록 포함)
  - 문의 관리: 상태 변경(접수 → 처리중 → 완료), 문의 삭제

## 배포 방법 (share.streamlit.io)

1. **MongoDB Atlas 준비**
   - https://cloud.mongodb.com 에서 무료 클러스터 생성 (M0)
   - Database Access에서 계정 생성, Network Access에서 `0.0.0.0/0` 허용 (Streamlit Cloud는 고정 IP가 아님)
   - "Connect" → "Drivers"에서 연결 문자열(`mongodb+srv://...`) 복사

2. **이 폴더를 GitHub 저장소에 push**
   - `.streamlit/secrets.toml` (실제 값이 든 파일)은 **절대 커밋하지 마세요**. 이미 예시 파일(`secrets.toml.example`)만 포함돼 있습니다.

3. **share.streamlit.io에서 새 앱 배포**
   - Repository / Branch / Main file path(`app.py`) 지정
   - Advanced settings → Secrets 에 아래 내용을 붙여넣기:
     ```toml
     MONGO_URI = "mongodb+srv://<username>:<password>@<cluster-url>/?retryWrites=true&w=majority"
     MONGO_DB_NAME = "hellini_routine"
     ADMIN_USERNAMES = "본인아이디"
     ```
     `ADMIN_USERNAMES`에 적은 아이디로 가입/로그인하면 사이드바에 "🛠️ 관리자 페이지" 메뉴가 보여요.
     여러 명을 관리자로 두려면 쉼표로 구분하면 됩니다. (예: `"me,friend1"`)
   - Deploy 클릭

앱이 처음 실행되면 자동으로 필요한 MongoDB 인덱스(유니크 인덱스 포함)를 생성합니다.

## 로컬 실행

```bash
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.toml 에 실제 MONGO_URI 입력 후
streamlit run app.py
```

## 데이터 구조 (MongoDB)

- `users`: `{username, salt, pw_hash, nickname, created_at}` — username, nickname 각각 unique index
- `logs`: `{user_id, date(YYYY-MM-DD), exercise_name, sets:[{w,r}], memo, created_at, updated_at}`
  — `(user_id, date, exercise_name)` unique index
- `inquiries`: `{user_id, nickname, category, content, created_at, status}`
- `presence`: `{user_id, username, nickname, last_seen}` — 페이지 로드마다 갱신, 현재 접속자 집계용

## 나중에 더 손볼 만한 부분
- 기존 HTML의 휴식 타이머, 세트 진행 애니메이션 등 UX 디테일은 아직 이식 안 함
- "현재 접속자"는 최근 5분 내 페이지 활동이 있었던 로그인 유저 수 기준 (완전 실시간 웹소켓 방식은 아님)
