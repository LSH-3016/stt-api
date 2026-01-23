# tracing.py
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

logger = logging.getLogger(__name__)

def setup_tracing(service_name: str = None):
    """OpenTelemetry 트레이싱 설정"""
    
    # 서비스 이름 설정 (환경변수 또는 파라미터)
    service = service_name or os.getenv("OTEL_SERVICE_NAME", "stt-api")
    
    # 리소스 정보 (서비스 메타데이터)
    resource = Resource.create({
        SERVICE_NAME: service,
        "service.version": os.getenv("APP_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENV", "production"),
    })
    
    # TracerProvider 설정
    provider = TracerProvider(resource=resource)
    
    # Jaeger로 트레이스 전송 (OTLP 프로토콜)
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True  # TLS 없이 연결 (개발용)
    )
    
    # BatchSpanProcessor: 트레이스를 모아서 일괄 전송 (성능 최적화)
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # 전역 TracerProvider 설정
    trace.set_tracer_provider(provider)
    
    logger.info(f"OpenTelemetry tracing initialized - service: {service}, endpoint: {otlp_endpoint}")
    
    return trace.get_tracer(__name__)
