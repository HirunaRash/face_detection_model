import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/splash_screen.dart'; 

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Supabase with your project details
  await Supabase.initialize(
    url: 'https://pfexlwikctosunnulxkp.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZXhsd2lrY3Rvc3VubnVseGtwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NjU3NzIsImV4cCI6MjA5NjA0MTc3Mn0.GqfBZSRBOPWh6oKUALXo2nvym9XkOZEmsK0VldeHzAA',
  );

  runApp(const BioIdAdminApp());
}

class BioIdAdminApp extends StatelessWidget {
  const BioIdAdminApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'BioID Admin',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
        useMaterial3: true,
      ),
      home: const SplashScreen(),
    );
  }
}