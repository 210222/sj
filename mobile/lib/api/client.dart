/// HTTP 客户端 — 统一 fetch 封装.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;
  final String? detail;

  const ApiException(this.statusCode, this.message, {this.detail});

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  final String baseUrl;
  final http.Client _http;

  ApiClient({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? ApiConfig.baseUrl,
        _http = client ?? http.Client();

  String? _token;

  void setToken(String? token) => _token = token;

  Map<String, String> get _headers {
    final h = <String, String>{
      'Content-Type': 'application/json',
    };
    if (_token != null) {
      h['Authorization'] = 'Bearer $_token';
    }
    return h;
  }

  Future<Map<String, dynamic>> get(String path,
      {Map<String, String>? queryParams}) async {
    final uri = Uri.parse('$baseUrl$path')
        .replace(queryParameters: queryParams);
    try {
      final resp = await _http
          .get(uri, headers: _headers)
          .timeout(ApiConfig.responseTimeout);
      return _handleResponse(resp);
    } on SocketException {
      throw const ApiException(0, 'Network error');
    } on TimeoutException {
      throw const ApiException(408, 'Request timeout');
    }
  }

  Future<Map<String, dynamic>> post(String path,
      {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    try {
      final resp = await _http
          .post(uri, headers: _headers, body: jsonEncode(body ?? {}))
          .timeout(ApiConfig.responseTimeout);
      return _handleResponse(resp);
    } on SocketException {
      throw const ApiException(0, 'Network error');
    } on TimeoutException {
      throw const ApiException(408, 'Request timeout');
    }
  }

  Map<String, dynamic> _handleResponse(http.Response resp) {
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    Map<String, dynamic>? detail;
    try {
      final body = jsonDecode(resp.body);
      if (body is Map<String, dynamic>) {
        detail = body['detail'] as Map<String, dynamic>?;
      }
    } catch (_) {}
    throw ApiException(
      resp.statusCode,
      detail?['error'] as String? ?? 'HTTP ${resp.statusCode}',
      detail: detail?['detail'] as String?,
    );
  }

  void dispose() => _http.close();
}
