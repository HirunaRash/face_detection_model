import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'login_page.dart'; // Local folder relative import

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  final _supabase = Supabase.instance.client;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Attendance Logs'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const LoginPage()),
              );
            },
          )
        ],
      ),
      body: StreamBuilder<List<Map<String, dynamic>>>(
        // Listen to changes in the attendance_logs table
        stream: _supabase
            .from('attendance_logs')
            .stream(primaryKey: ['id'])
            .order('arrival_time', ascending: false),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          
          final logs = snapshot.data ?? [];
          
          if (logs.isEmpty) {
            return const Center(child: Text('No attendance logs found.'));
          }

          return ListView.builder(
            padding: const EdgeInsets.all(8.0),
            itemCount: logs.length,
            itemBuilder: (context, index) {
              final log = logs[index];
              
              // Format the timestamp securely
              final arrivalTime = DateTime.parse(log['arrival_time'].toString());
              final formattedDate = '${arrivalTime.year}-${arrivalTime.month.toString().padLeft(2, '0')}-${arrivalTime.day.toString().padLeft(2, '0')}';
              final formattedTime = '${arrivalTime.hour.toString().padLeft(2, '0')}:${arrivalTime.minute.toString().padLeft(2, '0')}';

              return Card(
                elevation: 2,
                margin: const EdgeInsets.symmetric(vertical: 6.0),
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                    child: const Icon(Icons.how_to_reg),
                  ),
                  title: Text(
                    'Employee ID: ${log['employee_id']}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  subtitle: Text('Date: $formattedDate\nTime: $formattedTime'),
                  isThreeLine: true,
                ),
              );
            },
          );
        },
      ),
    );
  }
}