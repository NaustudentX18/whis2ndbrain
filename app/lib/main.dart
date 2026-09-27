import 'package:flutter/material.dart';
import 'api/api_client.dart';
import 'api/auth_store.dart';
import 'screens/setup_screen.dart';
import 'screens/shell_screen.dart';
import 'theme/whis_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const WhisApp());
}

class WhisApp extends StatelessWidget {
  const WhisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Whis2ndBrain',
      debugShowCheckedModeBanner: false,
      theme: whisTheme,
      home: const _Splash(),
    );
  }
}

class _Splash extends StatefulWidget {
  const _Splash();

  @override
  State<_Splash> createState() => _SplashState();
}

class _SplashState extends State<_Splash> {
  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    final configured = await AuthStore.isConfigured();
    if (!mounted) return;
    if (!configured) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const SetupScreen()),
      );
      return;
    }
    final host = (await AuthStore.getHostUrl())!;
    final token = (await AuthStore.getToken())!;
    final client = ApiClient(baseUrl: host, token: token);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ShellScreen(client: client)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Whis2ndBrain',
              style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                    color: cs.primary,
                    letterSpacing: 0.5,
                  ),
            ),
            const SizedBox(height: 24),
            CircularProgressIndicator(color: cs.primary),
          ],
        ),
      ),
    );
  }
}
