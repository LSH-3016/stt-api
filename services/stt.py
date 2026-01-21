import logging

logger = logging.getLogger(__name__)

# 실시간 스트리밍만 사용하므로 서비스 클래스 불필요
# WebSocket 라우터에서 직접 TranscribeStreamingClient 사용
