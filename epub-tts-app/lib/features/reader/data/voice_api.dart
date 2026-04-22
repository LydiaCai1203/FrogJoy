import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final voiceApiProvider = Provider<VoiceApi>((ref) {
  return VoiceApi(ref.watch(apiClientProvider));
});

class VoiceApi {
  final Dio _dio;

  VoiceApi(this._dio);

  Future<Response> getVoices() {
    return _dio.get('/voices');
  }

  Future<Response> getPreferences() {
    return _dio.get('/voices/preferences');
  }

  Future<Response> savePreferences(Map<String, dynamic> prefs) {
    return _dio.put('/voices/preferences', data: prefs);
  }
}
