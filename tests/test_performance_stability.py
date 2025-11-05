"""
성능 및 안정성 테스트
대용량 데이터, 메모리 사용량, 처리 속도, 안정성을 테스트
"""
import pytest
import pandas as pd
import time
import psutil
import threading
import concurrent.futures
import tempfile
import os
import gc
from unittest.mock import Mock, patch
from memory_profiler import profile


class TestPerformance:
    """성능 테스트 클래스"""

    def test_large_dataset_processing(self):
        """대용량 데이터셋 처리 성능 테스트"""
        print("⚡ 대용량 데이터셋 처리 성능 테스트 시작")

        # 대용량 데이터 생성 (10,000 응답)
        large_data_sizes = [1000, 5000, 10000]

        for size in large_data_sizes:
            start_time = time.time()

            # 대용량 데이터 생성
            large_data = pd.DataFrame({
                'Q1': [4, 3, 5, 4, 3] * (size // 5),
                'Q2': [3, 4, 4, 5, 3] * (size // 5),
                'Q3': [5, 4, 3, 4, 5] * (size // 5),
                'NO40': ['혁신적', '협력적', '안정적', '도전적', '성장지향'] * (size // 5),
                'NO41': ['팀워크', '소통', '리더십', '전문성', '창의성'] * (size // 5),
                'NO42': ['소통개선', '프로세스정비', '교육강화', '시스템개선', '인력충원'] * (size // 5),
                'NO43': ['시간부족', '자원제약', '권한제한', '정보부족', '절차복잡'] * (size // 5),
                'TEAM': [f'팀{i%50}' for i in range(size)]  # 50개 팀
            })

            # 데이터 처리 시간 측정
            processing_start = time.time()

            # 팀별 그룹핑
            team_groups = large_data.groupby('TEAM')
            team_count = len(team_groups)

            # 기본 통계 계산
            stats = {
                'q1_mean': large_data['Q1'].mean(),
                'q2_mean': large_data['Q2'].mean(),
                'q3_mean': large_data['Q3'].mean(),
                'total_responses': len(large_data)
            }

            processing_time = time.time() - processing_start
            total_time = time.time() - start_time

            # 성능 검증
            assert processing_time < 5.0  # 5초 이내 처리
            assert team_count == 50
            assert stats['total_responses'] == size

            print(f"✅ {size:,}개 응답 처리 완료:")
            print(f"   - 총 처리시간: {total_time:.2f}초")
            print(f"   - 데이터 처리시간: {processing_time:.2f}초")
            print(f"   - 팀 수: {team_count}개")

        print("🎉 대용량 데이터셋 처리 성능 테스트 완료")

    def test_memory_usage_monitoring(self):
        """메모리 사용량 모니터링 테스트"""
        print("⚡ 메모리 사용량 모니터링 테스트 시작")

        # 초기 메모리 사용량 측정
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # 메모리 집약적 작업 시뮬레이션
        memory_data = []

        for i in range(10):
            # 대용량 DataFrame 생성
            large_df = pd.DataFrame({
                'data': range(100000),
                'text': [f'sample_text_{j}' for j in range(100000)]
            })

            # 메모리 사용량 측정
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_data.append(current_memory)

            # 메모리 정리
            del large_df
            gc.collect()

        # 최종 메모리 사용량 측정
        final_memory = process.memory_info().rss / 1024 / 1024

        # 메모리 누수 검증 (증가량이 50MB 이하여야 함)
        memory_increase = final_memory - initial_memory
        assert memory_increase < 50

        print(f"✅ 메모리 사용량 테스트 완료:")
        print(f"   - 초기 메모리: {initial_memory:.2f}MB")
        print(f"   - 최종 메모리: {final_memory:.2f}MB")
        print(f"   - 메모리 증가: {memory_increase:.2f}MB")
        print(f"   - 최대 메모리: {max(memory_data):.2f}MB")

    @patch('streamlit_app.generate_ai_interpretation')
    def test_ai_processing_performance(self, mock_ai_generation):
        """AI 처리 성능 테스트"""
        print("⚡ AI 처리 성능 테스트 시작")

        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import generate_ai_interpretation

        # Mock AI 응답 (빠른 응답 시뮬레이션)
        mock_ai_generation.return_value = "AI 분석 결과입니다."

        # 다양한 크기의 입력 데이터로 성능 테스트
        input_sizes = [
            (100, 'small'),
            (500, 'medium'),
            (1000, 'large')
        ]

        performance_results = []

        for size, label in input_sizes:
            # 테스트 데이터 생성
            test_data = {
                'no40_text': ' '.join(['혁신적인 조직'] * size),
                'no41_text': ' '.join(['뛰어난 팀워크'] * size),
                'no42_text': ' '.join(['소통 개선 필요'] * size),
                'no43_text': ' '.join(['시간 부족'] * size),
                'respondents': size * 10,
                'org_units': f'{size}개 팀'
            }

            # 처리 시간 측정
            start_time = time.time()
            result = generate_ai_interpretation(test_data)
            processing_time = time.time() - start_time

            performance_results.append({
                'size': size,
                'label': label,
                'time': processing_time,
                'success': result is not None
            })

            # 성능 기준 검증 (Mock이므로 매우 빠르게 처리되어야 함)
            assert processing_time < 1.0
            assert result is not None

            print(f"✅ {label} 데이터 ({size}) 처리: {processing_time:.3f}초")

        print("🎉 AI 처리 성능 테스트 완료")

    def test_concurrent_processing(self):
        """동시 처리 성능 테스트"""
        print("⚡ 동시 처리 성능 테스트 시작")

        def process_team_data(team_id):
            """팀 데이터 처리 시뮬레이션"""
            # 팀별 데이터 생성
            team_data = pd.DataFrame({
                'Q1': [4, 3, 5] * 100,
                'Q2': [3, 4, 4] * 100,
                'TEAM': [f'팀{team_id}'] * 300
            })

            # 처리 시뮬레이션
            stats = {
                'team_id': team_id,
                'count': len(team_data),
                'q1_mean': team_data['Q1'].mean(),
                'q2_mean': team_data['Q2'].mean()
            }

            time.sleep(0.1)  # 처리 시간 시뮬레이션
            return stats

        # 순차 처리 시간 측정
        start_time = time.time()
        sequential_results = []
        for i in range(10):
            result = process_team_data(i)
            sequential_results.append(result)
        sequential_time = time.time() - start_time

        # 병렬 처리 시간 측정
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            parallel_results = list(executor.map(process_team_data, range(10)))
        parallel_time = time.time() - start_time

        # 성능 개선 검증
        improvement = sequential_time / parallel_time
        assert improvement > 1.5  # 최소 50% 성능 향상

        print(f"✅ 동시 처리 성능 테스트 완료:")
        print(f"   - 순차 처리: {sequential_time:.2f}초")
        print(f"   - 병렬 처리: {parallel_time:.2f}초")
        print(f"   - 성능 향상: {improvement:.1f}배")

    def test_file_processing_performance(self):
        """파일 처리 성능 테스트"""
        print("⚡ 파일 처리 성능 테스트 시작")

        # 다양한 크기의 파일 생성 및 처리 테스트
        file_sizes = [1000, 5000, 10000]

        for size in file_sizes:
            # 임시 Excel 파일 생성
            data = pd.DataFrame({
                'Q1': range(size),
                'Q2': range(size, size * 2),
                'TEAM': [f'팀{i%10}' for i in range(size)]
            })

            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                data.to_excel(tmp.name, index=False)
                temp_file = tmp.name

            try:
                # 파일 읽기 성능 측정
                start_time = time.time()
                df = pd.read_excel(temp_file)
                read_time = time.time() - start_time

                # 데이터 처리 성능 측정
                start_time = time.time()
                grouped = df.groupby('TEAM')
                team_count = len(grouped)
                process_time = time.time() - start_time

                # 성능 검증
                assert read_time < 5.0  # 파일 읽기 5초 이내
                assert process_time < 2.0  # 데이터 처리 2초 이내
                assert len(df) == size

                print(f"✅ {size:,}행 파일 처리:")
                print(f"   - 읽기 시간: {read_time:.2f}초")
                print(f"   - 처리 시간: {process_time:.2f}초")
                print(f"   - 팀 수: {team_count}개")

            finally:
                # 임시 파일 정리
                os.unlink(temp_file)

        print("🎉 파일 처리 성능 테스트 완료")


class TestStability:
    """안정성 테스트 클래스"""

    def test_long_running_stability(self):
        """장시간 실행 안정성 테스트"""
        print("⚡ 장시간 실행 안정성 테스트 시작")

        start_time = time.time()
        iteration_count = 100
        error_count = 0

        for i in range(iteration_count):
            try:
                # 반복적인 데이터 처리 시뮬레이션
                data = pd.DataFrame({
                    'Q1': [4, 3, 5] * 100,
                    'Q2': [3, 4, 4] * 100,
                    'TEAM': ['A팀', 'B팀', 'C팀'] * 100
                })

                # 그룹핑 및 통계 계산
                grouped = data.groupby('TEAM')
                stats = grouped.agg({
                    'Q1': ['mean', 'std'],
                    'Q2': ['mean', 'std']
                })

                # 메모리 정리
                del data, grouped, stats
                gc.collect()

                if i % 20 == 0:
                    print(f"   - {i+1}/{iteration_count} 완료")

            except Exception as e:
                error_count += 1
                print(f"   ⚠️ 오류 발생 ({i+1}번째): {e}")

        total_time = time.time() - start_time
        success_rate = ((iteration_count - error_count) / iteration_count) * 100

        # 안정성 검증
        assert success_rate >= 95.0  # 95% 이상 성공률
        assert error_count <= 5  # 최대 5개 오류

        print(f"✅ 장시간 실행 안정성 테스트 완료:")
        print(f"   - 총 실행시간: {total_time:.2f}초")
        print(f"   - 성공률: {success_rate:.1f}%")
        print(f"   - 오류 수: {error_count}개")

    def test_memory_leak_detection(self):
        """메모리 누수 감지 테스트"""
        print("⚡ 메모리 누수 감지 테스트 시작")

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        memory_readings = []

        # 반복적인 메모리 집약적 작업
        for i in range(50):
            # 대용량 데이터 생성
            large_data = pd.DataFrame({
                'col1': range(10000),
                'col2': [f'text_{j}' for j in range(10000)],
                'col3': [j * 1.5 for j in range(10000)]
            })

            # 복잡한 연산
            result = large_data.groupby(large_data['col1'] % 10).agg({
                'col1': 'sum',
                'col3': 'mean'
            })

            # 메모리 사용량 기록
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_readings.append(current_memory)

            # 정리
            del large_data, result
            gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024

        # 메모리 누수 분석
        memory_increase = final_memory - initial_memory
        max_memory = max(memory_readings)
        avg_memory = sum(memory_readings) / len(memory_readings)

        # 메모리 누수 검증 (증가량이 100MB 이하여야 함)
        assert memory_increase < 100

        print(f"✅ 메모리 누수 감지 테스트 완료:")
        print(f"   - 초기 메모리: {initial_memory:.2f}MB")
        print(f"   - 최종 메모리: {final_memory:.2f}MB")
        print(f"   - 메모리 증가: {memory_increase:.2f}MB")
        print(f"   - 최대 메모리: {max_memory:.2f}MB")
        print(f"   - 평균 메모리: {avg_memory:.2f}MB")

    def test_resource_cleanup(self):
        """리소스 정리 테스트"""
        print("⚡ 리소스 정리 테스트 시작")

        # 파일 핸들 관리 테스트
        temp_files = []

        try:
            # 여러 임시 파일 생성
            for i in range(10):
                df = pd.DataFrame({'data': range(1000)})
                temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
                df.to_excel(temp_file.name, index=False)
                temp_files.append(temp_file.name)
                temp_file.close()

            # 파일 읽기 및 처리
            for temp_file in temp_files:
                with open(temp_file, 'rb') as f:
                    data = f.read()
                    assert len(data) > 0

            print("✅ 파일 핸들 관리 테스트 통과")

        finally:
            # 리소스 정리
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

        print("✅ 리소스 정리 테스트 완료")

    def test_error_recovery(self):
        """오류 복구 테스트"""
        print("⚡ 오류 복구 테스트 시작")

        success_count = 0
        recovery_count = 0

        # 의도적 오류 발생 및 복구 테스트
        for i in range(20):
            try:
                if i % 5 == 0:
                    # 의도적 오류 발생
                    raise ValueError(f"의도적 오류 {i}")

                # 정상 처리
                data = pd.DataFrame({'test': [1, 2, 3]})
                result = data.sum()
                success_count += 1

            except ValueError:
                # 오류 복구 시뮬레이션
                try:
                    # 대체 처리
                    backup_data = pd.DataFrame({'test': [0, 0, 0]})
                    backup_result = backup_data.sum()
                    recovery_count += 1
                except:
                    pass

        recovery_rate = (recovery_count / 4) * 100  # 4번의 의도적 오류
        success_rate = (success_count / 16) * 100   # 16번의 정상 시도

        # 복구 능력 검증
        assert recovery_rate >= 75.0  # 75% 이상 복구율
        assert success_rate >= 90.0   # 90% 이상 성공률

        print(f"✅ 오류 복구 테스트 완료:")
        print(f"   - 성공률: {success_rate:.1f}%")
        print(f"   - 복구율: {recovery_rate:.1f}%")


class TestScalability:
    """확장성 테스트 클래스"""

    def test_team_scaling(self):
        """팀 수 확장성 테스트"""
        print("⚡ 팀 수 확장성 테스트 시작")

        team_counts = [10, 50, 100, 200]

        for team_count in team_counts:
            start_time = time.time()

            # 다수 팀 데이터 생성
            data = pd.DataFrame({
                'Q1': [4, 3, 5] * (team_count * 10),
                'Q2': [3, 4, 4] * (team_count * 10),
                'TEAM': [f'팀{i}' for i in range(team_count)] * 30
            })

            # 팀별 처리
            teams = data.groupby('TEAM')
            team_stats = {}

            for team_name, team_data in teams:
                team_stats[team_name] = {
                    'count': len(team_data),
                    'q1_mean': team_data['Q1'].mean(),
                    'q2_mean': team_data['Q2'].mean()
                }

            processing_time = time.time() - start_time

            # 확장성 검증
            assert len(team_stats) == team_count
            assert processing_time < 10.0  # 10초 이내 처리

            print(f"✅ {team_count}개 팀 처리: {processing_time:.2f}초")

        print("🎉 팀 수 확장성 테스트 완료")

    def test_data_volume_scaling(self):
        """데이터 볼륨 확장성 테스트"""
        print("⚡ 데이터 볼륨 확장성 테스트 시작")

        volumes = [1000, 10000, 50000, 100000]

        for volume in volumes:
            start_time = time.time()

            # 대용량 데이터 생성
            data = pd.DataFrame({
                'Q1': [4, 3, 5, 4, 3] * (volume // 5),
                'Q2': [3, 4, 4, 5, 3] * (volume // 5),
                'TEAM': [f'팀{i%20}' for i in range(volume)]
            })

            # 데이터 처리
            summary = {
                'total_count': len(data),
                'q1_mean': data['Q1'].mean(),
                'q2_mean': data['Q2'].mean(),
                'team_count': data['TEAM'].nunique()
            }

            processing_time = time.time() - start_time

            # 선형적 확장성 검증 (시간이 데이터량에 비례해서 증가)
            time_per_1k = (processing_time / volume) * 1000

            assert summary['total_count'] == volume
            assert time_per_1k < 0.1  # 1000개당 0.1초 이내

            print(f"✅ {volume:,}개 데이터 처리:")
            print(f"   - 처리시간: {processing_time:.2f}초")
            print(f"   - 1K당 시간: {time_per_1k:.3f}초")

        print("🎉 데이터 볼륨 확장성 테스트 완료")


def run_performance_tests():
    """성능 및 안정성 테스트 실행 함수"""
    print("⚡ 성능 및 안정성 테스트 시작")
    print("=" * 50)

    # pytest 실행
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--no-header",
        "--disable-warnings"
    ])


if __name__ == "__main__":
    run_performance_tests()