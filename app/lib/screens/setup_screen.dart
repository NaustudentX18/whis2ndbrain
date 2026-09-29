import 'package:flutter/material.dart';
import '../api/api_client.dart';
import '../api/auth_store.dart';
import 'shell_screen.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  final _formKey = GlobalKey<FormState>();
  // Real tailnet origin (TLS, LE cert via tailscale serve); loopback only for on-host tests.
  final _hostController =
      TextEditingController(text: 'https://omarchy.tail9760ad.ts.net:8765');
  final _tokenController = TextEditingController();

  bool _isTesting = false;
  bool _isSaving = false;
  String? _statusMessage;
  bool _statusSuccess = false;

  @override
  void dispose() {
    _hostController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  String _cleanUrl(String raw) {
    var url = raw.trim();
    if (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    return url;
  }

  Future<void> _testConnection() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isTesting = true;
      _statusMessage = null;
    });

    final url = _cleanUrl(_hostController.text);
    final token = _tokenController.text.trim();
    final client = ApiClient(baseUrl: url, token: token);

    try {
      final ready = await client.isReady();
      if (!ready) {
        throw Exception('Server health responded unready.');
      }
      // Check auth by fetching settings
      await client.getSettings();
      setState(() {
        _statusSuccess = true;
        _statusMessage = 'Connection successful! Host is ready & token valid.';
      });
    } catch (e) {
      setState(() {
        _statusSuccess = false;
        _statusMessage = 'Connection failed: $e';
      });
    } finally {
      setState(() {
        _isTesting = false;
      });
    }
  }

  Future<void> _saveAndContinue() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isSaving = true;
      _statusMessage = null;
    });

    final url = _cleanUrl(_hostController.text);
    final token = _tokenController.text.trim();

    try {
      await AuthStore.setHostUrl(url);
      await AuthStore.setToken(token);

      final client = ApiClient(baseUrl: url, token: token);
      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => ShellScreen(client: client)),
      );
    } catch (e) {
      setState(() {
        _statusSuccess = false;
        _statusMessage = 'Failed to save configuration: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Connect to Whis2ndBrain'),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Icon(Icons.mic_none_outlined, size: 64, color: cs.primary),
                    const SizedBox(height: 16),
                    Text(
                      'Host Connection',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            color: cs.onSurface,
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Enter your review server address and owner authentication token to pair this device.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: const Color(0xFFB2C9C4),
                          ),
                    ),
                    const SizedBox(height: 32),
                    TextFormField(
                      controller: _hostController,
                      keyboardType: TextInputType.url,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Host Server URL',
                        hintText: 'http://127.0.0.1:8765 or http://100.x.x.x:8765',
                        prefixIcon: Icon(Icons.dns_outlined),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Host URL is required';
                        }
                        final uri = Uri.tryParse(value.trim());
                        if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
                          return 'Enter a valid URL (e.g. http://192.168.1.50:8765)';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _tokenController,
                      obscureText: true,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Owner Auth Token',
                        hintText: 'Paste token from /data/whis2ndbrain/review/token',
                        prefixIcon: Icon(Icons.key_outlined),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return 'Owner token is required';
                        }
                        return null;
                      },
                    ),
                    if (_statusMessage != null) ...[
                      const SizedBox(height: 20),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: _statusSuccess
                              ? const Color(0xFF003829)
                              : const Color(0xFF93000A),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              _statusSuccess
                                  ? Icons.check_circle_outline
                                  : Icons.error_outline,
                              color: _statusSuccess
                                  ? cs.primary
                                  : cs.onError,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                _statusMessage!,
                                style: TextStyle(
                                  color: _statusSuccess
                                      ? cs.primary
                                      : cs.onError,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 32),
                    OutlinedButton.icon(
                      onPressed: _isTesting || _isSaving ? null : _testConnection,
                      icon: _isTesting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.wifi_tethering),
                      label: Text(_isTesting ? 'Testing...' : 'Test Connection'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      onPressed: _isTesting || _isSaving ? null : _saveAndContinue,
                      icon: _isSaving
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.black,
                              ),
                            )
                          : const Icon(Icons.arrow_forward),
                      label: Text(_isSaving ? 'Connecting...' : 'Save & Continue'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
