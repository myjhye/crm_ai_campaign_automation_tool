"""Synthetic name parts; generated combinations do not identify real people."""
from hashlib import sha256

SURNAMES = tuple('김 이 박 최 정 강 조 윤 장 임 한 오 서 신 권 황 안 송 전 홍 유 고 문 양 손 배 백 허 남 심 노 하 곽 성 차 주 우 구 민 진'.split())
GIVEN_NAMES = tuple('가온 가람 가율 가윤 가은 겨울 고운 구름 나래 나린 나봄 나빛 나예 나온 나율 나윤 나은 나찬 누리 다경 다나 다빈 다솔 다솜 다온 다원 다율 다윤 다은 다인 단아 도담 도아 도연 도영 도원 도윤 라온 라율 라윤 라희 로아 로운 루나 루리 마루 마음 모아 미루 미리 미소 바다 바람 반디 보라 보름 봄결 봄빛 빛나 사라 새나 새론 새봄 새솔 새온 새하 서린 서아 서온 서우 서율 선율 소담 소라 소리 소민 소율 솔비 솔아 수린 수아 수안 수연 수온 수율 슬아 시아 시온 시우 아라 아린 아온 아윤 아인 여름 여울 연두 예나 예담 예린 예솔 예온 예원 예율 오름 온결 온유 우림 우솔 유나 유라 유리 유안 유온 유하 윤슬 은결 은솔 은유 은하 이든 이랑 이솔 이안 이온 재이 정원 주아 지안 지온 지우 지율 찬솔 초아 초원 하늘 하람 하린 하온 하율 한결 한별 한빛 한솔 해나 해솔 해온 혜온 호수'.split())


def synthetic_name(external_id: str, seed: int) -> str:
    digest = sha256(f'korean-name-v1:{seed}:{external_id}'.encode()).digest()
    return SURNAMES[int.from_bytes(digest[:8], 'big') % len(SURNAMES)] + GIVEN_NAMES[int.from_bytes(digest[8:16], 'big') % len(GIVEN_NAMES)]
