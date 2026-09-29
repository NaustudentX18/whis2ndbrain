import 'dart:convert';
import 'package:http/http.dart' as http;

/// Client for the Whis2ndBrain review server API.
///
/// All requests are authenticated with a Bearer token stored in
/// flutter_secure_storage. The client throws [ApiException] for all
/// non-2xx responses so callers can handle them uniformly.
class ApiClient {
  final String baseUrl; // e.g. "https://omarchy.tail9760ad.ts.net:8765"
  final String token;

  const ApiClient({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  /// Auth headers for media players streaming audio outside package:http
  /// (the host requires the Authorization header; token-in-URL never worked).
  Map<String, String> get audioHeaders => {
        'Authorization': 'Bearer $token',
        'Accept': 'audio/wav',
      };

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = Uri.parse(baseUrl);
    return base.replace(
      path: path,
      queryParameters: query,
    );
  }

  Future<Map<String, dynamic>> _get(String path,
      [Map<String, String>? query]) async {
    final resp = await http.get(_uri(path, query), headers: _headers);
    return _parse(resp);
  }

  Future<Map<String, dynamic>> _patch(String path, Map<String, dynamic> body,
      [Map<String, String>? extraHeaders]) async {
    final resp = await http.patch(
      _uri(path),
      headers: {..._headers, ...?extraHeaders},
      body: jsonEncode(body),
    );
    return _parse(resp);
  }

  Future<Map<String, dynamic>> _post(String path,
      [Map<String, dynamic>? body]) async {
    final resp = await http.post(
      _uri(path),
      headers: _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _parse(resp);
  }

  Future<Map<String, dynamic>> _delete(String path) async {
    final resp = await http.delete(_uri(path), headers: _headers);
    return _parse(resp);
  }

  Map<String, dynamic> _parse(http.Response resp) {
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      if (resp.body.isEmpty) return {};
      return jsonDecode(resp.body) as Map<String, dynamic>;
    }
    String message;
    try {
      message = (jsonDecode(resp.body) as Map)['error'] as String? ??
          resp.body;
    } catch (_) {
      message = resp.body;
    }
    throw ApiException(resp.statusCode, message);
  }

  // ── Health ────────────────────────────────────────────────────────────────

  Future<bool> isReady() async {
    try {
      final data = await _get('/api/v1/health/ready');
      return data['status'] == 'ready';
    } catch (_) {
      return false;
    }
  }

  // ── Notes ─────────────────────────────────────────────────────────────────

  /// Keyset cursor pagination when [cursor] is given (stable under new
  /// captures); [includeDeleted] lists tombstoned notes (trash view).
  Future<NotesPage> listNotes({
    String? status,
    String? search,
    int limit = 50,
    int offset = 0,
    String? cursor,
    bool includeDeleted = false,
  }) async {
    final query = <String, String>{
      'limit': '$limit',
      'offset': '$offset',
      if (status != null) 'status': status,
      if (search != null && search.isNotEmpty) 'search': search,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
      if (includeDeleted) 'include_deleted': 'true',
    };
    final data = await _get('/api/v1/notes', query);
    return NotesPage.fromJson(data);
  }

  Future<Note> getNote(String captureId) async {
    final data = await _get('/api/v1/notes/$captureId');
    return Note.fromJson(data);
  }

  /// Patches a note. With [revision], sends `If-Match` for optimistic
  /// concurrency: a 412 [ApiException] means the note changed elsewhere -
  /// reload and reapply; the first writer's edit is the one that survived.
  Future<Note> patchNote(String captureId, Map<String, dynamic> patch,
      {int? revision}) async {
    final data = await _patch('/api/v1/notes/$captureId', patch, {
      if (revision != null) 'if-match': '"$revision"',
    });
    return Note.fromJson(data);
  }

  /// Tombstones a note (hidden from lists; rows and held audio retained).
  Future<void> deleteNote(String captureId) async {
    await _delete('/api/v1/notes/$captureId');
  }

  /// Clears a tombstone.
  Future<void> restoreNote(String captureId) async {
    await _post('/api/v1/notes/$captureId/restore');
  }

  /// Owner-requested retry of an exhausted transcription job.
  Future<void> retryTranscription(String captureId) async {
    await _post('/api/v1/notes/$captureId/retry');
  }

  // ── Settings ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getSettings() => _get('/api/v1/settings');

  Future<Map<String, dynamic>> patchSettings(Map<String, dynamic> updates) =>
      _patch('/api/v1/settings', updates);

  // ── Telemetry ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getTelemetry() =>
      _get('/api/v1/device/telemetry');

  Future<Map<String, dynamic>> sendHeartbeat(
          [Map<String, dynamic>? data]) =>
      _post('/api/v1/device/heartbeat', data);

  // ── Audio (streamed by the player with [audioHeaders]; byte-range capable)

  String audioUrl(String captureId) =>
      '$baseUrl/api/v1/notes/$captureId/audio';
}

// ── Models ────────────────────────────────────────────────────────────────────

class Note {
  final String captureId;
  final String status;
  final String? transcript;
  final String? transcriptSource;
  final String? receivedAt;
  final String? audioPurgedAt;
  final String? category;
  final String? urgency;
  final bool? actionable;
  final String? deletedAt;
  final int revision;

  const Note({
    required this.captureId,
    required this.status,
    this.transcript,
    this.transcriptSource,
    this.receivedAt,
    this.audioPurgedAt,
    this.category,
    this.urgency,
    this.actionable,
    this.deletedAt,
    this.revision = 0,
  });

  factory Note.fromJson(Map<String, dynamic> j) => Note(
        captureId: j['capture_id'] as String,
        status: j['status'] as String,
        transcript: j['transcript'] as String?,
        transcriptSource: j['transcript_source'] as String?,
        receivedAt: j['received_at'] as String?,
        audioPurgedAt: j['audio_purged_at'] as String?,
        category: j['category'] as String?,
        urgency: j['urgency'] as String?,
        actionable: j['actionable'] as bool?,
        deletedAt: j['deleted_at'] as String?,
        revision: (j['revision'] as num?)?.toInt() ?? 0,
      );

  bool get hasAudio => audioPurgedAt == null;
  bool get isOwnerCorrected => transcriptSource == 'owner';
  bool get isTranscribed =>
      status == 'transcribed' || status == 'reviewed';
  bool get isDeleted => deletedAt != null;
}

class NotesPage {
  final List<Note> items;
  final int total;
  final int limit;
  final int offset;
  final String? nextCursor;

  const NotesPage(
      {required this.items,
      required this.total,
      required this.limit,
      required this.offset,
      this.nextCursor});

  factory NotesPage.fromJson(Map<String, dynamic> j) => NotesPage(
        items: (j['items'] as List)
            .map((e) => Note.fromJson(e as Map<String, dynamic>))
            .toList(),
        total: j['total'] as int,
        limit: j['limit'] as int,
        offset: j['offset'] as int,
        nextCursor: j['next_cursor'] as String?,
      );

  /// Cursor-first: a present cursor means another page exists. Falls back
  /// to offset arithmetic for hosts that do not send cursors.
  bool get hasMore => nextCursor != null ||
      (nextCursor == null && items.isNotEmpty && offset + items.length < total);
}

// ── Exception ─────────────────────────────────────────────────────────────────

class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException(this.statusCode, this.message);

  bool get isConflict => statusCode == 412;

  @override
  String toString() => 'ApiException($statusCode): $message';
}
