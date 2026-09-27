import 'package:flutter_test/flutter_test.dart';
import 'package:whis_app/api/api_client.dart';

void main() {
  group('Note model tests', () {
    test('fromJson parses Note with full fields', () {
      final json = {
        'capture_id': 'cap-101',
        'status': 'transcribed',
        'transcript': 'Hello world testing voice capture',
        'transcript_source': 'model',
        'received_at': '2026-09-27T08:00:00Z',
        'audio_purged_at': null,
        'category': 'thought',
        'urgency': 'normal',
        'actionable': false,
      };

      final note = Note.fromJson(json);

      expect(note.captureId, 'cap-101');
      expect(note.status, 'transcribed');
      expect(note.transcript, 'Hello world testing voice capture');
      expect(note.transcriptSource, 'model');
      expect(note.hasAudio, isTrue);
      expect(note.isOwnerCorrected, isFalse);
      expect(note.isTranscribed, isTrue);
      expect(note.category, 'thought');
      expect(note.urgency, 'normal');
      expect(note.actionable, isFalse);
    });

    test('hasAudio is false when audio_purged_at is present', () {
      final json = {
        'capture_id': 'cap-102',
        'status': 'reviewed',
        'transcript': 'Purged note audio test',
        'transcript_source': 'owner',
        'received_at': '2026-09-20T08:00:00Z',
        'audio_purged_at': '2026-09-27T08:00:00Z',
        'category': 'todo',
        'urgency': 'high',
        'actionable': true,
      };

      final note = Note.fromJson(json);

      expect(note.hasAudio, isFalse);
      expect(note.isOwnerCorrected, isTrue);
      expect(note.actionable, isTrue);
    });

    test('NotesPage parses page with items and total', () {
      final json = {
        'items': [
          {
            'capture_id': 'cap-1',
            'status': 'received',
            'transcript': null,
            'transcript_source': null,
            'received_at': '2026-09-27T08:00:00Z',
            'audio_purged_at': null,
            'category': null,
            'urgency': null,
            'actionable': null,
          }
        ],
        'total': 1,
        'limit': 50,
        'offset': 0,
      };

      final page = NotesPage.fromJson(json);

      expect(page.items.length, 1);
      expect(page.items.first.captureId, 'cap-1');
      expect(page.total, 1);
      expect(page.hasMore, isFalse);
    });
  });

  group('ApiClient helper tests', () {
    test('audioUrl builds valid authenticated streaming URL', () {
      const client = ApiClient(baseUrl: 'http://127.0.0.1:8765', token: 'secret-token-xyz');
      final url = client.audioUrl('cap-abc-123');

      expect(url, 'http://127.0.0.1:8765/n/cap-abc-123/audio?token=secret-token-xyz');
    });
  });
}
