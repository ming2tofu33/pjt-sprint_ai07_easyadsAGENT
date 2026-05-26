# Secrets 관리

이 프로젝트의 API key와 token은 코드에 직접 작성하지 않는다.

- OpenAI API key: `.env`의 `OPENAI_API_KEY`
- Hugging Face token: `.env`의 `HF_TOKEN`
- `.env`는 git에 commit하지 않는다.
- 공유가 필요한 값은 팀 비밀 관리 채널 또는 배포 서버 환경변수로 관리한다.

