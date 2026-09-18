# 개발용 스크립트

`python -m scripts.enqueue_worker_check`는 진단용 dataset과 작업을 같은 트랜잭션으로 생성한다.
`python -m scripts.run_db_tests --create`는 전용 테스트 DB를 준비하고 전체 테스트를 실행한다.
단계 3에서 고객 샘플 데이터 생성 명령을 추가한다.
스크립트는 앱 import 시 자동 실행하지 않고 명시적으로 실행한다.
