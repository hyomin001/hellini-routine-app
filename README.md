# 헬린이 루틴 (Streamlit)

기존 로컬 저장(localStorage) HTML 앱을 로그인 + 공용 랭킹 + 문의 게시판이 있는
멀티유저 Streamlit 앱으로 재구성한 버전입니다.

## 기능
- 회원가입/로그인 (아이디·비밀번호·닉네임, 전부 중복 불가)
  - 회원가입 시 비밀번호 찾기용 **보안 질문** 등록, 로그인 화면의 "비밀번호 찾기" 탭에서 본인 확인 후 직접 재설정 가능
- 오늘의 루틴 기록 (DAY1~4, 세트별 무게/횟수 입력, 메모, 숫자 검증)
  - 날짜 선택 시 부위 1~4를 합산한 "이 날짜 전체 N/M 완료" 진행 요약을 상단에 표시
  - 60/90/120초 휴식 타이머 (페이지 전체에서 공용 1개, 다른 운동을 저장해서 화면이 다시 그려져도 남은 시간이 끊기지 않고 이어짐)
  - 🔥 오늘 인증 현황: 그 날짜에 누가 몇 종목을 기록했는지 실시간으로 보여줌 (같이 방송 보며 운동할 때 동기부여용)
- 마이페이지
  - 상단에 🔥연속 기록일 · 🗓️총 기록일 · 🏋️총 볼륨(무게×횟수 합) 요약 + 최근 14주 잔디밭(히트맵) 캘린더
  - 🏅 개인 최고기록(PR) + 운동별 무게 추이 라인 그래프
  - 🎖️ 뱃지: 연속기록/누적기록일/총볼륨/챔피언/올라운더 등 11종 업적, 달성 여부 카드로 표시
  - 🗓️ 날짜별 기록 히스토리 (수정/삭제 가능)
  - ⚙️ 계정 설정: 닉네임 변경, 비밀번호 변경, 보안 질문 설정/변경, **내 기록 CSV 다운로드**, 회원 탈퇴(본인이 직접, 비밀번호 확인 후)
- 랭킹
  - 👑 전체 종목 1위: 23개 운동 각각의 현재 챔피언(닉네임/무게/횟수)을 한 번에 확인
  - 📋 종목별 TOP 20: 운동 하나를 골라 순위표(최고 무게, 동률 시 최고 횟수)로 확인 + TOP20 밖이어도 내 순위 항상 표시
  - 🏋️ 총 볼륨 랭킹: 모든 운동의 무게×횟수를 합산한 전체 유저 순위 (꾸준함 동기부여용) + 내 순위 표시
- 문의하기: 운동 추가 요청 / 기능 개선 / 버그 신고 / 기타, 전체 공개 게시판 + 내 문의만 보기
  - 관리자가 남긴 답변이 있으면 문의 아래에 공개로 함께 표시
- 실시간 현황: 화면 상단에 총 가입자 수 / 현재 접속자 수(최근 5분 내 활동 기준) / 내 연속 기록일 상시 표시
- 관리자 페이지 (`ADMIN_USERNAMES`로 지정한 계정만 접근 가능)
  - 대시보드: 총 가입자·현재 접속자·총 기록 수·미처리 문의 수, 지금 접속 중인 사람 목록, 종목별 챔피언 요약, 최근 14일 가입 추이 차트
  - 회원 관리: 전체 회원 검색/조회, 계정 삭제(기록 포함), **비밀번호 강제 초기화**(임시 비밀번호 발급 — 보안 질문을 등록 안 했거나 잊은 회원 구제용)
  - 문의 관리: 상태 변경(접수 → 처리중 → 완료), 답변 작성/수정, 문의 삭제

## 화면 이동 방식
사이드바가 아니라 로그인 후 보이는 화면 상단의 버튼(🏠 오늘 / 📖 기록 / 🏆 랭킹 / 💬 문의 / 🛠️ 관리)으로 페이지를 전환합니다. `pages/` 폴더 방식의 Streamlit 멀티페이지가 아니라 `app.py` 하나에서 `st.session_state`로 화면을 바꾸는 단일 페이지 구조라, 모바일에서도 사이드바를 펼칠 필요 없이 바로 버튼이 보여요. (예전에 남아있던 `pages/*.py` 사이드바 기반 구버전 화면들은 이 구조와 중복·충돌하는 죽은 코드라 정리했습니다.)

## 관리자 계정 만들기
1. 앱에서 **회원가입** 탭으로 아이디 `admin`, 비밀번호 `0727`, 원하는 닉네임으로 가입합니다. (비밀번호는 4자 이상이면 되고, 배포 후 원하면 바꿔도 됩니다)
2. Streamlit Cloud의 Secrets에 `ADMIN_USERNAMES = "admin"` 을 추가합니다. (아래 배포 방법 참고)
3. `admin` 계정으로 로그인하면 상단 버튼에 "🛠️ 관리자"가 나타납니다.

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
     ADMIN_USERNAMES = "admin"
     ```
     `ADMIN_USERNAMES`에 적은 아이디로 가입/로그인하면 상단 버튼에 "🛠️ 관리자"가 보여요.
     여러 명을 관리자로 두려면 쉼표로 구분하면 됩니다. (예: `"admin,friend1"`)
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

- `users`: `{username, salt, pw_hash, nickname, created_at, security_question?, security_answer_salt?, security_answer_hash?}` — username, nickname 각각 unique index
  - `security_question` 계열 필드는 가입 시 또는 마이페이지 계정설정에서 나중에 등록 가능. 기존에 이 필드 없이 가입한 유저는 "비밀번호 찾기"를 못 쓰고, 관리자가 회원 관리 탭의 "비밀번호 강제 초기화"로 구제해줘야 함
- `logs`: `{user_id, date(YYYY-MM-DD), exercise_name, sets:[{w,r}], memo, created_at, updated_at}`
  — `(user_id, date, exercise_name)` unique index
- `inquiries`: `{user_id, nickname, category, content, created_at, status, answer?, answered_at?}`
- `presence`: `{user_id, username, nickname, last_seen}` — 페이지 로드마다 갱신, 현재 접속자 집계용

## 나중에 더 손볼 만한 부분
- "현재 접속자"는 최근 5분 내 페이지 활동이 있었던 로그인 유저 수 기준 (완전 실시간 웹소켓 방식은 아님)
- "운동 추가 요청" 문의가 들어와도 실제 운동 추가는 `utils/exercises_data.json`을 직접 수정하고 재배포해야 함 — 관리자가 웹에서 바로 운동을 추가/수정하게 하려면 이 데이터를 DB로 옮기는 작업이 필요함 (이번 업데이트에서는 손대지 않음, 다음 단계로 남겨둠)
- 휴식 타이머는 브라우저 `localStorage`로 남은 시간을 유지하는 방식이라, 기기를 바꾸거나 시크릿 모드로 들어오면 이어지지 않음 (기기 하나로 계속 쓰는 일반적인 경우엔 문제 없음)

