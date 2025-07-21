"""
개선된 파일 관리 유틸리티
- 파일명 PREFIX 제거
- 다중 파일 업로드 지원
- 압축 파일 처리
"""
import re
import zipfile
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any
import mimetypes

# RAR 지원은 선택적으로 (라이브러리가 설치된 경우에만)
try:
    import rarfile

    RAR_SUPPORTED = True
except ImportError:
    RAR_SUPPORTED = False


class FileNameCleaner:
    """파일명 정리 및 표시 관리"""

    @staticmethod
    def clean_display_name(filename: str) -> str:
        """
        표시용 파일명에서 PREFIX 제거

        Args:
            filename: 원본 파일명 (예: "61ce979e-d764-4d90-9965-e78e4df2a235_ERP_설치가이드.txt")

        Returns:
            정리된 파일명 (예: "ERP_설치가이드.txt")
        """
        # UUID 패턴 제거 (32자리 16진수 + 하이픈들)
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_'
        cleaned = re.sub(uuid_pattern, '', filename, flags=re.IGNORECASE)

        # 추가 패턴들 제거
        patterns_to_remove = [
            r'^[0-9a-f]{32}_',  # 32자리 16진수
            r'^[0-9a-f]+_',  # 일반적인 해시값
            r'^timestamp_\d+_',  # 타임스탬프 prefix
            r'^tmp_[0-9a-f]+_',  # 임시 파일 prefix
            r'^file_[0-9a-f]+_',  # file_ prefix
        ]

        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # # 연속된 언더스코어 정리
        # cleaned = re.sub(r'_{2,}', '_', cleaned)
        #
        # # 앞뒤 언더스코어 제거
        # cleaned = cleaned.strip('_')

        return cleaned if cleaned else filename  # 빈 문자열이면 원본 반환

    @staticmethod
    def extract_file_info(filename: str) -> Dict[str, str]:
        """
        파일명에서 정보 추출

        Returns:
            dict: {
                'original': 원본 파일명,
                'display': 표시용 파일명,
                'prefix': 제거된 PREFIX,
                'extension': 확장자,
                'basename': 확장자 없는 이름
            }
        """
        display_name = FileNameCleaner.clean_display_name(filename)
        path_obj = Path(display_name)

        return {
            'original': filename,
            'display': display_name,
            'prefix': filename.replace(display_name, '').rstrip('_'),
            'extension': path_obj.suffix.lower(),
            'basename': path_obj.stem
        }


class MultiFileProcessor:
    """다중 파일 및 압축 파일 처리"""

    SUPPORTED_ARCHIVE_FORMATS = ['.zip']  # 기본적으로 ZIP만 지원
    if RAR_SUPPORTED:
        SUPPORTED_ARCHIVE_FORMATS.extend(['.rar'])

    SUPPORTED_DOCUMENT_FORMATS = ['.pdf', '.docx', '.doc', '.txt', '.md', '.rtf']
    SUPPORTED_IMAGE_FORMATS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']

    @staticmethod
    def get_supported_formats() -> List[str]:
        """지원되는 파일 형식 목록 반환"""
        return (MultiFileProcessor.SUPPORTED_DOCUMENT_FORMATS +
                MultiFileProcessor.SUPPORTED_IMAGE_FORMATS +
                MultiFileProcessor.SUPPORTED_ARCHIVE_FORMATS)

    @staticmethod
    def is_archive_file(filename: str) -> bool:
        """압축 파일 여부 확인"""
        ext = Path(filename).suffix.lower()
        return ext in MultiFileProcessor.SUPPORTED_ARCHIVE_FORMATS

    @staticmethod
    def is_supported_document(filename: str) -> bool:
        """지원되는 문서 파일 여부 확인"""
        ext = Path(filename).suffix.lower()
        return ext in (MultiFileProcessor.SUPPORTED_DOCUMENT_FORMATS +
                       MultiFileProcessor.SUPPORTED_IMAGE_FORMATS)

    @staticmethod
    def extract_archive_contents(archive_file, max_files: int = 50) -> List[Dict]:
        """
        압축 파일 내용 추출 및 분석

        Args:
            archive_file: 업로드된 압축 파일
            max_files: 최대 추출 파일 수

        Returns:
            List[Dict]: 추출된 파일 정보 목록
        """
        extracted_files = []

        try:
            # ZIP 파일 처리
            if archive_file.name.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                    file_list = zip_ref.namelist()[:max_files]  # 최대 파일 수 제한

                    for file_path in file_list:
                        if not file_path.endswith('/'):  # 디렉토리 제외
                            filename = os.path.basename(file_path)
                            if MultiFileProcessor.is_supported_document(filename):
                                try:
                                    content = zip_ref.read(file_path)
                                    file_info = {
                                        'name': filename,
                                        'content': content,
                                        'size': len(content),
                                        'path_in_archive': file_path,
                                        'type': mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                                    }
                                    extracted_files.append(file_info)
                                except Exception as e:
                                    print(f"파일 추출 실패: {file_path} - {e}")

            # RAR 파일 처리 (rarfile 라이브러리가 설치된 경우에만)
            elif archive_file.name.lower().endswith('.rar') and RAR_SUPPORTED:
                try:
                    with rarfile.RarFile(archive_file, 'r') as rar_ref:
                        file_list = rar_ref.namelist()[:max_files]

                        for file_path in file_list:
                            if not file_path.endswith('/'):
                                filename = os.path.basename(file_path)
                                if MultiFileProcessor.is_supported_document(filename):
                                    try:
                                        content = rar_ref.read(file_path)
                                        file_info = {
                                            'name': filename,
                                            'content': content,
                                            'size': len(content),
                                            'path_in_archive': file_path,
                                            'type': mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                                        }
                                        extracted_files.append(file_info)
                                    except Exception as e:
                                        print(f"RAR 파일 추출 실패: {file_path} - {e}")
                except Exception as e:
                    raise Exception(f"RAR 파일 처리 실패: {str(e)}")

        except Exception as e:
            raise Exception(f"압축 파일 처리 실패: {str(e)}")

        return extracted_files

    @staticmethod
    def validate_archive_file(archive_file, max_size_mb: float = 100) -> Tuple[bool, str]:
        """압축 파일 유효성 검사"""

        # 파일 크기 확인
        file_size_mb = archive_file.size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"압축 파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 지원됩니다."

        # 파일 형식 확인
        if not MultiFileProcessor.is_archive_file(archive_file.name):
            return False, "지원하지 않는 압축 파일 형식입니다."

        # 압축 파일 무결성 확인 (기본적인 체크)
        try:
            if archive_file.name.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                    # 압축 파일이 손상되었는지 확인
                    bad_file = zip_ref.testzip()
                    if bad_file:
                        return False, f"압축 파일이 손상되었습니다: {bad_file}"
        except zipfile.BadZipFile:
            return False, "올바르지 않은 ZIP 파일입니다."
        except Exception as e:
            return False, f"압축 파일 검증 실패: {str(e)}"

        return True, "OK"


class FileUploadManager:
    """파일 업로드 관리 통합 클래스"""

    def __init__(self, max_file_size_mb: float = 50, max_archive_size_mb: float = 100):
        self.max_file_size_mb = max_file_size_mb
        self.max_archive_size_mb = max_archive_size_mb
        self.file_processor = MultiFileProcessor()
        self.name_cleaner = FileNameCleaner()

    def process_uploaded_files(self, uploaded_files: List) -> Dict[str, Any]:
        """
        업로드된 파일들을 처리

        Args:
            uploaded_files: Streamlit에서 업로드된 파일 목록

        Returns:
            Dict: 처리 결과 정보
        """
        results = {
            'success_files': [],
            'failed_files': [],
            'extracted_files': [],
            'total_files': 0,
            'errors': []
        }

        for uploaded_file in uploaded_files:
            try:
                # 압축 파일인지 확인
                if self.file_processor.is_archive_file(uploaded_file.name):
                    # 압축 파일 처리
                    is_valid, error_msg = self.file_processor.validate_archive_file(
                        uploaded_file, self.max_archive_size_mb
                    )

                    if is_valid:
                        try:
                            extracted = self.file_processor.extract_archive_contents(uploaded_file)
                            results['extracted_files'].extend(extracted)
                            results['success_files'].append({
                                'name': uploaded_file.name,
                                'type': 'archive',
                                'extracted_count': len(extracted)
                            })
                        except Exception as e:
                            results['failed_files'].append({
                                'name': uploaded_file.name,
                                'error': str(e)
                            })
                            results['errors'].append(f"압축 파일 처리 실패: {uploaded_file.name} - {str(e)}")
                    else:
                        results['failed_files'].append({
                            'name': uploaded_file.name,
                            'error': error_msg
                        })
                        results['errors'].append(f"{uploaded_file.name}: {error_msg}")

                else:
                    # 일반 파일 처리
                    if self.file_processor.is_supported_document(uploaded_file.name):
                        # 파일 크기 검사
                        file_size_mb = uploaded_file.size / (1024 * 1024)
                        if file_size_mb <= self.max_file_size_mb:
                            results['success_files'].append({
                                'name': uploaded_file.name,
                                'type': 'document',
                                'size': uploaded_file.size,
                                'file_obj': uploaded_file
                            })
                        else:
                            error_msg = f"파일 크기가 너무 큽니다 ({file_size_mb:.1f}MB > {self.max_file_size_mb}MB)"
                            results['failed_files'].append({
                                'name': uploaded_file.name,
                                'error': error_msg
                            })
                            results['errors'].append(f"{uploaded_file.name}: {error_msg}")
                    else:
                        error_msg = "지원하지 않는 파일 형식입니다"
                        results['failed_files'].append({
                            'name': uploaded_file.name,
                            'error': error_msg
                        })
                        results['errors'].append(f"{uploaded_file.name}: {error_msg}")

            except Exception as e:
                results['failed_files'].append({
                    'name': uploaded_file.name,
                    'error': str(e)
                })
                results['errors'].append(f"파일 처리 중 오류: {uploaded_file.name} - {str(e)}")

        results['total_files'] = len(results['success_files']) + len(results['extracted_files'])

        return results

    def format_file_list_for_display(self, file_list: List[Dict]) -> List[Dict]:
        """
        파일 목록을 표시용으로 포맷

        Args:
            file_list: 원본 파일 목록

        Returns:
            List[Dict]: 표시용 파일 정보 목록
        """
        formatted_list = []

        for file_info in file_list:
            file_name = file_info.get('name', '')
            cleaned_info = self.name_cleaner.extract_file_info(file_name)

            formatted_file = {
                'display_name': cleaned_info['display'],
                'original_name': cleaned_info['original'],
                'extension': cleaned_info['extension'],
                'basename': cleaned_info['basename'],
                'size': file_info.get('size', 'Unknown'),
                'time': file_info.get('time', 'Unknown'),
                'chunks': file_info.get('chunks', 0),
                'type': file_info.get('type', 'document')
            }

            formatted_list.append(formatted_file)

        return formatted_list


class FileUtils:
    """파일 관련 유틸리티 함수들"""

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형식으로 변환"""
        if size_bytes == 0:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    @staticmethod
    def validate_file(file, allowed_extensions: List[str], max_size_mb: float = 50) -> Tuple[bool, str]:
        """파일 유효성 검사"""
        # 파일 확장자 확인
        file_extension = Path(file.name).suffix.lower().lstrip('.')
        if file_extension not in allowed_extensions:
            return False, f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"

        # 파일 크기 확인
        file_size_mb = file.size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 지원됩니다."

        # MIME 타입 확인 (추가 보안)
        mime_type = mimetypes.guess_type(file.name)[0]
        if mime_type and not any(mime_type.startswith(t) for t in ['text/', 'application/', 'image/']):
            return False, "잘못된 파일 형식입니다."

        return True, "OK"

    @staticmethod
    def get_file_icon(file_extension: str) -> str:
        """파일 확장자에 따른 아이콘 반환"""
        icons = {
            'pdf': '📄',
            'doc': '📝', 'docx': '📝',
            'txt': '📃', 'md': '📃',
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
            'bmp': '🖼️', 'tiff': '🖼️',
            'zip': '📦', 'rar': '📦', '7z': '📦',
            'csv': '📊', 'xlsx': '📊', 'xls': '📊',
            'json': '🔧', 'xml': '🔧',
            'py': '🐍', 'js': '🟨',
            'html': '🌐', 'css': '🎨'
        }

        return icons.get(file_extension.lower(), '📎')

# 편의 함수들
def get_supported_file_formats() -> List[str]:
    """지원되는 파일 형식 목록 (편의 함수)"""
    return MultiFileProcessor.get_supported_formats()

def format_file_list_with_clean_names(file_list: List[Dict]) -> List[Dict]:
    """
    파일 목록의 이름을 정리해서 반환

    Args:
        file_list: 원본 파일 목록

    Returns:
        정리된 파일 목록
    """
    cleaned_list = []

    for file_info in file_list.copy():
        # 원본 정보 복사
        cleaned_file = file_info.copy()

        # 파일명 정리
        original_name = file_info.get('name', '')
        display_name = FileNameCleaner.clean_display_name(original_name)

        # 정리된 이름으로 업데이트
        cleaned_file['name'] = display_name
        cleaned_file['original_name'] = original_name

        cleaned_list.append(cleaned_file)

    return cleaned_list

def extract_file_info_batch(filenames: List[str]) -> List[Dict]:
    """
    여러 파일명의 정보를 일괄 추출

    Args:
        filenames: 파일명 목록

    Returns:
        파일 정보 목록
    """
    file_info_list = []

    for filename in filenames:
        info = FileNameCleaner.extract_file_info(filename)
        file_info_list.append(info)

    return file_info_list
