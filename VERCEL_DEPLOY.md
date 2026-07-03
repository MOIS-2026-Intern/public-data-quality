# Vercel 배포

이 저장소는 Vercel에서 프론트엔드는 Vite 정적 빌드로, 백엔드는 Flask 기반 Python Function으로 배포됩니다.

## Vercel 프로젝트 설정

- Root Directory: 저장소 루트
- Install Command: `npm --prefix frontend ci`
- Build Command: `npm --prefix frontend run build`
- Output Directory: `frontend/dist`

위 값은 `vercel.json`에 이미 들어 있으므로 Vercel 대시보드에서 별도로 덮어쓰지 않아도 됩니다.

## 로컬 확인

```bash
npm --prefix frontend ci
npm --prefix frontend run build
python3 -c "from api.index import app; client=app.test_client(); print(client.get('/api/health').status_code)"
```

## 배포

```bash
npx vercel
```

프로덕션 배포:

```bash
npx vercel --prod
```

## 주의사항

- OpenAI API Key는 프론트 입력값으로 요청마다 전달됩니다. Vercel 환경변수에 저장하지 않아도 됩니다.
- Vercel Python Function은 서버리스 환경이므로 생성 CSV는 배포 파일 시스템이 아니라 `/tmp/validation`에 기록됩니다.
- 분석 시간이 길면 Vercel Function 제한에 걸릴 수 있습니다. 현재 `api/index.py`의 `maxDuration`은 60초로 설정했습니다.
- `vercel.json`의 rewrites는 Vercel wildcard parameter 형식인 `/:path*`를 사용합니다.
