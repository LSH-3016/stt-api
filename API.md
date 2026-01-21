# STT API 문서

## 기본 정보

- Base URL: `https://stt.aws11.shop`
- 엔진: Amazon Transcribe Streaming
- 지원 언어: 한국어 (ko-KR)

## 엔드포인트

### 1. 실시간 STT (WebSocket)

실시간 음성 스트림을 텍스트로 변환합니다.

**URL**: `wss://stt.aws11.shop/stt/stream`

**오디오 요구사항**:
- 포맷: PCM (raw)
- 샘플레이트: 16kHz
- 채널: 모노
- 비트: 16bit (Int16)

**클라이언트 → 서버**: 바이너리 오디오 청크

**서버 → 클라이언트**:
```json
{
  "text": "현재 인식된 텍스트",
  "full_text": "전체 누적 텍스트",
  "is_final": false
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| text | string | 현재 세그먼트 텍스트 |
| full_text | string | 전체 누적 텍스트 |
| is_final | boolean | `false`: 중간 결과 (업데이트됨), `true`: 최종 결과 |

**에러 응답**:
```json
{
  "error": "에러 메시지",
  "text": "",
  "is_final": false
}
```

**JavaScript 예시**:
```javascript
const ws = new WebSocket('wss://stt.aws11.shop/stt/stream');

// AudioContext로 16kHz PCM 변환
const audioContext = new AudioContext({ sampleRate: 16000 });
const processor = audioContext.createScriptProcessor(2048, 1, 1);

processor.onaudioprocess = (e) => {
  const float32 = e.inputBuffer.getChannelData(0);
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
  }
  ws.send(int16.buffer);
};

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  if (result.is_final) {
    console.log('최종:', result.text);
  } else {
    console.log('중간:', result.text);
  }
};
```

---

### 2. Health Check

**URL**: `GET /health` 또는 `GET /stt/health`

**응답**:
```json
{
  "status": "healthy",
  "service": "stt",
  "engine": "amazon-transcribe-streaming",
  "streaming": "enabled"
}
```

---

## 권장 클라이언트 설정

### 오디오 캡처
- 샘플레이트: 16000Hz
- 버퍼 크기: 2048 (약 128ms)
- 채널: 모노

### WebSocket
- 연결 유지: ping/pong 사용
- 재연결: 지수 백오프 적용
- 종료 시: 정상 close 호출

### Partial Results 처리
```javascript
let confirmedText = '';
let partialText = '';

ws.onmessage = (event) => {
  const { text, is_final } = JSON.parse(event.data);
  
  if (is_final) {
    confirmedText += text + ' ';
    partialText = '';
  } else {
    partialText = text;
  }
  
  display(confirmedText + partialText);
};
```
