import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final readingStatsApiProvider = Provider<ReadingStatsApi>((ref) {
  return ReadingStatsApi(ref.watch(apiClientProvider));
});

class ReadingStatsApi {
  final Dio _dio;
  ReadingStatsApi(this._dio);

  /// GET /reading/stats/summary → { total_seconds, streak_days, books_count }
  Future<Map<String, dynamic>> getSummary() async {
    final res = await _dio.get('/reading/stats/summary');
    return res.data as Map<String, dynamic>;
  }

  /// GET /reading/stats/heatmap?year=2026 → [{ date, seconds }, ...]
  Future<List<Map<String, dynamic>>> getHeatmap(int year) async {
    final res = await _dio.get('/reading/stats/heatmap', queryParameters: {'year': year});
    return (res.data as List).cast<Map<String, dynamic>>();
  }

  /// GET /reading/stats/books → [{ book_id, title, cover_url, total_seconds, last_read_date }, ...]
  Future<List<Map<String, dynamic>>> getBookStats() async {
    final res = await _dio.get('/reading/stats/books');
    return (res.data as List).cast<Map<String, dynamic>>();
  }
}
