# Threads 자동발행 셋업 가이드

> 마케팅 콘텐츠 공장(MARKETING.md) **Phase 2** — 스레드(Threads) 자동발행을 위한
> 토큰 발급 절차. 본인 1개 계정에만 발행하므로 OAuth 웹플로우 없이
> **한 번만 수동으로 토큰을 뽑아 Secret에 저장**하면 된다.
>
> 마지막 업데이트: 2026-06-26

---

## 0. 큰 그림

```
[Meta 앱 생성] → [Threads 권한 설정] → [본인을 테스터로 추가]
   → [브라우저 1회 인증 → code] → [code → 단기토큰 + user_id]
   → [단기 → 장기토큰(60일)] → [Secret 저장] → 끝
```

확보해야 할 최종 결과물 **딱 2개**:

| 값 | 어디서 나오나 | 저장할 Secret 이름 |
|----|----------------|---------------------|
| 장기 액세스 토큰 | 6단계 응답 `access_token` | `THREADS_ACCESS_TOKEN` |
| 숫자 user_id | 5단계 응답 `user_id` | `THREADS_USER_ID` |

> ⚠️ "스레드 ID"는 두 종류다.
> - **핸들** `@axislytics` = 사람이 보는 이름 (직접 찾을 필요 없음)
> - **숫자 user_id** `17841...` = **API가 쓰는 진짜 ID** = `THREADS_USER_ID` (5단계에서 자동 발급)

---

## 사전 준비

- [ ] 발행용 **Threads 계정** (브랜드/익명 계정 권장 — 개인 계정과 분리)
- [ ] 계정이 **공개(Public)** 상태 — 비공개면 API 발행 불가
- [ ] 연결된 **인스타그램 계정** (Threads는 IG에 종속. 새로 만들면 IG도 함께 생성됨)
- [ ] Meta 개발자 계정 (https://developers.facebook.com)

---

## 1단계 — Meta 앱 생성

1. https://developers.facebook.com/apps → **앱 만들기(Create App)**
2. Use case: **"Threads API에 액세스(Access the Threads API)"** 선택
3. 생성 후 **앱 설정 → 기본 설정(Settings → Basic)** 에서 복사:
   - **앱 ID** (`<APP_ID>`)
   - **앱 시크릿** (`<APP_SECRET>`)  ← 노출 금지

---

## 2단계 — Threads 권한·리디렉션 설정

1. 좌측 메뉴 **Threads API 사용 사례 → 설정(Use cases → Settings)**
2. **권한(scope)** 체크:
   - `threads_basic` (필수)
   - `threads_content_publish` (발행 필수)
3. **리디렉션 콜백 URI(Redirect Callback URLs)** 에 본인 통제 HTTPS URL 등록
   - 예: `https://axislytics.com/`
   - (실제 콜백 처리 코드는 불필요 — 인증 후 주소창에 `?code=...`가 붙어 돌아오는 용도)

---

## 3단계 — 본인을 Threads 테스터로 추가

1. **앱 역할 → 역할(App roles → Roles)** → **사람 추가(Add People)** → **Threads Tester** 로 본인 추가
2. **Threads 앱/웹 → 설정 → 계정 → 웹사이트 권한(Website permissions)** 에서 **초대 수락**

> 이 단계를 빼먹으면 4단계 인증에서 권한 거부가 난다.

---

## 4단계 — 브라우저로 인증 코드(code) 1회 받기

아래 URL을 본인 값으로 치환해 **브라우저 주소창**에 입력:

```
https://threads.net/oauth/authorize?client_id=<APP_ID>&redirect_uri=https://axislytics.com/&scope=threads_basic,threads_content_publish&response_type=code
```

→ 승인하면 `https://axislytics.com/?code=AQB...#_` 로 리디렉션.
→ 주소창에서 **`code=` 뒤 값**만 복사 (끝의 `#_`는 **제외**).

> code는 **1시간** 유효. 바로 5단계로 진행.

---

## 5단계 — code → 단기 토큰 + user_id 교환

터미널에서 (Claude Code 세션이면 `!` 프리픽스로 바로 실행 가능):

```bash
curl -s -X POST "https://graph.threads.net/oauth/access_token" \
  -d client_id=<APP_ID> \
  -d client_secret=<APP_SECRET> \
  -d grant_type=authorization_code \
  -d redirect_uri=https://axislytics.com/ \
  -d code=<4단계_CODE>
```

응답 예:
```json
{ "access_token": "THQ...(단기)", "user_id": 17841412345678901 }
```
→ `user_id` 값이 곧 **`THREADS_USER_ID`** (메모해 둘 것)
→ `access_token` 은 **단기(1시간)** — 바로 6단계로 장기 전환

---

## 6단계 — 단기(1h) → 장기(60일) 토큰 교환

```bash
curl -s "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=<APP_SECRET>&access_token=<5단계_단기토큰>"
```

응답 예:
```json
{ "access_token": "THQ...(장기)", "token_type": "bearer", "expires_in": 5184000 }
```
→ 이 `access_token` 이 **`THREADS_ACCESS_TOKEN`** (5,184,000초 = 60일)

---

## 7단계 — Secret 저장 (Cloud Run · 프로젝트 all-of-asset)

```bash
# 최초 생성
echo -n "<장기토큰>"        | gcloud secrets create THREADS_ACCESS_TOKEN --data-file=- --project=all-of-asset
echo -n "<user_id_숫자>"    | gcloud secrets create THREADS_USER_ID      --data-file=- --project=all-of-asset

# 이미 있으면 새 버전 추가
echo -n "<장기토큰>"        | gcloud secrets versions add THREADS_ACCESS_TOKEN --data-file=- --project=all-of-asset
```

그리고 Cloud Run 서비스(`stock-screener`)에 시크릿을 env로 연결 (배포 스크립트에서 `--set-secrets`).

---

## 8단계 — 60일마다 토큰 갱신

장기 토큰은 60일 만료. 만료 전 1회 호출로 60일 연장:

```bash
curl -s "https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token=<현재_장기토큰>"
```

> 추후 **Cloud Run Job 월 1회 스케줄**로 자동 회전(refresh → Secret 새 버전 add) 가능.

---

## 참고 — 발행 API 동작 (토큰 준비 후 구현)

Base URL: `https://graph.threads.net/v1.0`

**2단계 발행**:
1. 컨테이너 생성
   ```
   POST /{THREADS_USER_ID}/threads
     ?media_type=TEXT
     &text=<본문>
     &access_token=<TOKEN>
   → { "id": "<creation_id>" }
   ```
2. 발행
   ```
   POST /{THREADS_USER_ID}/threads_publish
     ?creation_id=<creation_id>
     &access_token=<TOKEN>
   → { "id": "<published_post_id>" }
   ```

**제약**:
- 텍스트 **500자**
- 하루 **250개**
- 이미지 첨부 시 `media_type=IMAGE` + `image_url`(공개 HTTPS URL 필요)
  → 기존 `/stocks/[ticker]/opengraph-image` OG 카드 재활용 가능

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| 인증 시 권한 거부 | 3단계 테스터 추가/수락 누락 |
| `code` 가 안 붙음 | 리디렉션 URI가 앱에 등록된 값과 정확히 일치해야 함 (슬래시까지) |
| 토큰 교환 400 | code 만료(1시간) — 4단계부터 다시 |
| 발행 시 비공개 오류 | 계정이 비공개 — 공개로 전환 |
| user_id 못 찾음 | 5단계 응답에 포함 — 별도 조회 불필요 |

---

## 체크리스트 (확보 후)

- [ ] `THREADS_USER_ID` (숫자)
- [ ] `THREADS_ACCESS_TOKEN` (장기, 60일)
- [ ] 두 값 Cloud Run Secret 저장
- [ ] 60일 갱신 일정/알림 설정

→ 이 둘이 채워지면 코드 측 작업은 `utils/threads_client.py` + 발행 라우트 + `/admin/marketing` 발행 버튼 + (선택) 예약발행 Job.
