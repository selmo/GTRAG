#!/usr/bin/env python3
"""
GTOne RAG System API 테스트 스크립트
시스템이 정상적으로 작동하는지 확인합니다.
"""
import requests
import json
import time
import sys
from pathlib import Path

# API 기본 URL
API_BASE_URL = "http://localhost:8000"

# 색상 코드
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'


def print_test(name, passed, message=""):
    """테스트 결과 출력"""
    if passed:
        print(f"{GREEN}✅ {name}{NC}")
    else:
        print(f"{RED}❌ {name}{NC}")
        if message:
            print(f"   {message}")


def test_health_check():
    """헬스 체크 테스트"""
    try:
        response = requests.get(f"{API_BASE_URL}/v1/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_test("Health Check", True)

            # 서비스별 상태 확인
            services = data.get('services', {})

            # Qdrant 상태
            qdrant_status = services.get('qdrant', {}).get('status') == 'connected'
            print_test("  - Qdrant", qdrant_status)

            # Ollama 상태
            ollama_status = services.get('ollama', {}).get('status') == 'connected'
            print_test("  - Ollama", ollama_status)

            # Celery 상태
            celery_status = services.get('celery', {}).get('status') == 'connected'
            print_test("  - Celery", celery_status)

            return True
        else:
            print_test("Health Check", False, f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_test("Health Check", False, str(e))
        return False


def test_document_upload():
    """문서 업로드 테스트"""
    try:
        # 테스트 파일 생성
        test_content = """
        This is a test document for GTOne RAG System.
        이것은 GTOne RAG 시스템의 테스트 문서입니다.

        주요 기능:
        - 문서 업로드
        - 벡터 검색
        - RAG 기반 답변
        """

        files = {
            'file': ('test_document.txt', test_content.encode('utf-8'), 'text/plain')
        }

        response = requests.post(f"{API_BASE_URL}/v1/documents", files=files, timeout=30)

        if response.status_code == 200:
            data = response.json()
            chunks = data.get('uploaded', 0)
            print_test("Document Upload", chunks > 0, f"Uploaded {chunks} chunks")
            return chunks > 0
        else:
            print_test("Document Upload", False, f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_test("Document Upload", False, str(e))
        return False


def test_search():
    """검색 기능 테스트"""
    try:
        # 문서 업로드 후 약간 대기
        time.sleep(2)

        response = requests.get(
            f"{API_BASE_URL}/v1/search",
            params={"q": "테스트 문서", "top_k": 3},
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()
            print_test("Search", True, f"Found {len(results)} results")

            # 결과 내용 확인
            if results:
                print(f"  첫 번째 결과 점수: {results[0].get('score', 0):.3f}")

            return True
        else:
            print_test("Search", False, f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_test("Search", False, str(e))
        return False


def test_rag_answer():
    """RAG 답변 생성 테스트"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/v1/rag/answer",
            params={"q": "GTOne RAG 시스템의 주요 기능은?", "top_k": 3},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            has_answer = bool(data.get('answer'))
            print_test("RAG Answer Generation", has_answer)

            if has_answer:
                print(f"  답변 길이: {len(data['answer'])} 자")
                sources = data.get('sources', [])
                print(f"  참조 문서: {len(sources)} 개")

            return has_answer
        else:
            print_test("RAG Answer Generation", False, f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_test("RAG Answer Generation", False, str(e))
        return False


def test_api_docs():
    """API 문서 접근 테스트"""
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        passed = response.status_code == 200
        print_test("API Documentation", passed)
        return passed
    except Exception as e:
        print_test("API Documentation", False, str(e))
        return False


def test_streamlit_ui():
    """Streamlit UI 접근 테스트"""
    try:
        response = requests.get("http://localhost:8501", timeout=5)
        passed = response.status_code == 200
        print_test("Streamlit UI", passed)
        return passed
    except Exception as e:
        print_test("Streamlit UI", False, str(e))
        return False


def main():
    """메인 테스트 실행"""
    print("=" * 50)
    print("GTOne RAG System API 테스트")
    print("=" * 50)

    # API 서버 준비 대기
    print("\nAPI 서버 연결 확인 중...")
    max_retries = 6
    for i in range(max_retries):
        try:
            requests.get(f"{API_BASE_URL}/health", timeout=2)
            print(f"{GREEN}API 서버 연결 성공!{NC}")
            break
        except:
            if i < max_retries - 1:
                print(f"연결 시도 {i + 1}/{max_retries}...")
                time.sleep(5)
            else:
                print(f"{RED}API 서버에 연결할 수 없습니다.{NC}")
                sys.exit(1)

    print("\n테스트 시작...\n")

    # 테스트 실행
    tests = [
        ("기본 연결", [test_api_docs, test_streamlit_ui]),
        ("시스템 상태", [test_health_check]),
        ("핵심 기능", [test_document_upload, test_search, test_rag_answer])
    ]

    total_tests = 0
    passed_tests = 0

    for category, test_funcs in tests:
        print(f"\n{YELLOW}[{category}]{NC}")
        for test_func in test_funcs:
            if test_func():
                passed_tests += 1
            total_tests += 1
            time.sleep(1)  # 테스트 간 대기

    # 결과 요약
    print("\n" + "=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    print(f"전체 테스트: {total_tests}")
    print(f"성공: {GREEN}{passed_tests}{NC}")
    print(f"실패: {RED}{total_tests - passed_tests}{NC}")

    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    if success_rate == 100:
        print(f"\n{GREEN}✅ 모든 테스트 통과! 시스템이 정상적으로 작동합니다.{NC}")
    elif success_rate >= 70:
        print(f"\n{YELLOW}⚠️  일부 테스트 실패. 시스템 점검이 필요합니다.{NC}")
    else:
        print(f"\n{RED}❌ 대부분의 테스트 실패. 시스템에 문제가 있습니다.{NC}")

    print("\n상세 로그 확인: docker compose logs -f")


if __name__ == "__main__":
    main()