import time

from app.config import settings
from loguru import logger

class CircuitBreaker:
    """
    ES 장애 시 일정 시간 동안 요청 차단
    CLOSED -> OPEN -> CLOSED 상태로 전환
    """
    def __init__(self):
        self.is_open = False
        self.opened_at = None

    def record_failure(self):
        """ES 에러 발생 시 OPEN 상태로 전환"""
        self.is_open = True
        self.opened_at = time.time()
        logger.warning("Circuit Breaker OPEN")

    def check(self) -> bool:
        """
        현재 Circuit 상태 확인
        True = OPEN (요청 차단), False = CLOSED (정상)
        """
        if not self.is_open:
            return False

        elapsed = time.time() - self.opened_at
        if elapsed >= settings.CB_OPEN_DURATION:
            self.is_open = False
            self.opened_at = None
            logger.info("Circuit Breaker CLOSED")
            return False

        return True


circuit_breaker = CircuitBreaker()