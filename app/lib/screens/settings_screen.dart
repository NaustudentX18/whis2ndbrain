import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/auth_store.dart';
import 'setup_screen.dart';

class SettingsScreen extends StatefulWidget {
  final ApiClient client;

  const SettingsScreen({super.key, required this.client});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _vaultPathController = TextEditingController();
  final _keyFileController = TextEditingController();

  double _retentionHours = 168.0;
  bool _encryptionEnabled = false;
  bool _driveEnabled = false;
  bool _transcriptionEnabled = true;
  bool _suggestionsEnabled = true;
  String? _deviceId;
  String? _driveLastBackupAt;

  bool _isLoading = false;
  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    _vaultPathController.dispose();
    _keyFileController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final s = await widget.client.getSettings();
      setState(() {
        _retentionHours = (s['retention_hours'] as num?)?.toDouble() ?? 168.0;
        _vaultPathController.text = s['vault_export_path'] as String? ?? '';
        _encryptionEnabled = s['encryption_enabled'] as bool? ?? false;
        _keyFileController.text = s['encryption_key_file'] as String? ?? '';
        _driveEnabled = s['drive_enabled'] as bool? ?? false;
        _driveLastBackupAt = s['drive_last_backup_at'] as String?;
        _transcriptionEnabled = s['transcription_enabled'] as bool? ?? true;
        _suggestionsEnabled = s['suggestion_categories_enabled'] as bool? ?? true;
        _deviceId = s['device_id'] as String?;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load settings: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _saveSettings() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    final updates = <String, dynamic>{
      'retention_hours': _retentionHours.toInt(),
      'encryption_enabled': _encryptionEnabled,
      'drive_enabled': _driveEnabled,
      'transcription_enabled': _transcriptionEnabled,
      'suggestion_categories_enabled': _suggestionsEnabled,
    };

    if (_vaultPathController.text.trim().isNotEmpty) {
      updates['vault_export_path'] = _vaultPathController.text.trim();
    }
    if (_keyFileController.text.trim().isNotEmpty) {
      updates['encryption_key_file'] = _keyFileController.text.trim();
    }

    try {
      await widget.client.patchSettings(updates);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved successfully')),
        );
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to save settings: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  Future<void> _disconnect() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Disconnect from Host?'),
        content: const Text(
          'This will clear the stored host URL and token from this app. '
          'You will need to re-enter them to connect again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Disconnect'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      await AuthStore.clear();
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const SetupScreen()),
        (route) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Hardware & App Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _loadSettings,
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_errorMessage != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF93000A),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _errorMessage!,
                style: const TextStyle(color: Colors.white),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Section 1: Obsidian Vault & Export
          _sectionCard(
            title: 'Obsidian Vault & Export',
            icon: Icons.folder_open,
            cs: cs,
            children: [
              TextFormField(
                controller: _vaultPathController,
                decoration: const InputDecoration(
                  labelText: 'Vault Inbox Path',
                  hintText: '/home/forest/Documents/Vault/Inbox',
                  helperText: 'Absolute path for Markdown export dispatch',
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Audio Retention: ${_retentionHours.toInt()} hours (${(_retentionHours / 24).toStringAsFixed(1)} days)',
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
              Slider(
                value: _retentionHours,
                min: 24,
                max: 720,
                divisions: 29,
                label: '${_retentionHours.toInt()}h',
                onChanged: (val) => setState(() => _retentionHours = val),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Section 2: Security & At-Rest Encryption
          _sectionCard(
            title: 'Security & At-Rest Encryption',
            icon: Icons.lock_outline,
            cs: cs,
            children: [
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('AES-256-GCM Audio Encryption'),
                subtitle: const Text('Encrypt new audio captures on disk before write'),
                value: _encryptionEnabled,
                onChanged: (val) => setState(() => _encryptionEnabled = val),
              ),
              if (_encryptionEnabled) ...[
                const SizedBox(height: 12),
                TextFormField(
                  controller: _keyFileController,
                  decoration: const InputDecoration(
                    labelText: 'Key File Path',
                    hintText: '/data/whis2ndbrain/review/audio.key',
                    helperText: 'Must be mode 0o600 on host',
                  ),
                ),
              ],
            ],
          ),

          const SizedBox(height: 16),

          // Section 3: Google Drive Sync
          _sectionCard(
            title: 'Google Drive Secondary Backup',
            icon: Icons.cloud_upload_outlined,
            cs: cs,
            children: [
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Enable Google Drive Backup'),
                subtitle: const Text('Sync encrypted audio & database to Drive folder'),
                value: _driveEnabled,
                onChanged: (val) => setState(() => _driveEnabled = val),
              ),
              if (_driveLastBackupAt != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    'Last Backup: ${_driveLastBackupAt!.replaceFirst('T', ' ').replaceFirst('Z', ' UTC')}',
                    style: const TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ),
            ],
          ),

          const SizedBox(height: 16),

          // Section 4: Transcription & AI
          _sectionCard(
            title: 'AI & Transcription Engine',
            icon: Icons.psychology_outlined,
            cs: cs,
            children: [
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Automatic Background Transcription'),
                subtitle: const Text('Run faster-whisper worker on newly queued audio'),
                value: _transcriptionEnabled,
                onChanged: (val) => setState(() => _transcriptionEnabled = val),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Categorization & Urgency Suggestions'),
                subtitle: const Text('Extract meeting/todo/idea classification from speech'),
                value: _suggestionsEnabled,
                onChanged: (val) => setState(() => _suggestionsEnabled = val),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Section 5: Connection Info & Disconnect
          _sectionCard(
            title: 'Host Connection & Hardware',
            icon: Icons.link,
            cs: cs,
            children: [
              Text(
                'Host URL: ${widget.client.baseUrl}',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
              ),
              if (_deviceId != null) ...[
                const SizedBox(height: 6),
                Text(
                  'Paired Device: $_deviceId',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                ),
              ],
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _disconnect,
                icon: const Icon(Icons.link_off, color: Colors.red),
                label: const Text('Disconnect from Host', style: TextStyle(color: Colors.red)),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // Save button
          FilledButton.icon(
            onPressed: _isSaving ? null : _saveSettings,
            icon: _isSaving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black),
                  )
                : const Icon(Icons.save),
            label: Text(_isSaving ? 'Saving...' : 'Save Settings'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _sectionCard({
    required String title,
    required IconData icon,
    required ColorScheme cs,
    required List<Widget> children,
  }) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: cs.primary, size: 22),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const Divider(height: 24),
            ...children,
          ],
        ),
      ),
    );
  }
}
