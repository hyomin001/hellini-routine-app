# 헬린이 루틴 (Streamlit)

기존 로컬 저장(localStorage) HTML 앱을 로그인 + 공용 랭킹 + 문의 게시판이 있는
멀티유저 Streamlit 앱으로 재구성한 버전입니다.

## 기능
- 회원가입/로그인 (아이디·비밀번호·닉네임, 전부 중복 불가)
- 오늘의 루틴 기록 (DAY1~4, 세트별 무게/횟수 입력, 메모)
- 마이페이지: 운동별 개인 최고기록(PR) + 날짜별 기록 히스토리 (삭제 가능)
- 랭킹: 운동별로 최고 무게(동률 시 최고 횟수) 기준 리더보드
- 문의하기: 운동 추가 요청 / 기능 개선 / 버그 신고 / 기타, 전체 공개 게시판 + 내 문의만 보기

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
     ```
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

## 나중에 더 손볼 만한 부분
- 기존 HTML의 휴식 타이머, 세트 진행 애니메이션 등 UX 디테일은 아직 이식 안 함
- 운동 아이콘/사진은 뺐음 (원하면 st.image로 추가 가능)
- 문의 상태(`status`)를 관리자만 바꿀 수 있는 관리자 페이지는 없음 (필요하면 요청해주세요)
