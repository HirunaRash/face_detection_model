import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'dart:math';
import 'login_page.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage>
    with TickerProviderStateMixin {
  final _supabase = Supabase.instance.client;
  late AnimationController _headerRotateController;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  String _searchQuery = '';
  String _filterType = 'All';
  final _searchController = TextEditingController();

  // Stats
  int _todayCount = 0;
  int _totalCount = 0;

  @override
  void initState() {
    super.initState();
    _headerRotateController = AnimationController(
      duration: const Duration(seconds: 12),
      vsync: this,
    )..repeat();

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 0.7, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _headerRotateController.dispose();
    _pulseController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  void _confirmLogout() {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: const Color(0xFF0D1E30),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(
              color: Colors.white.withValues(alpha: 0.1), width: 1),
        ),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.redAccent.withValues(alpha: 0.1),
                  border: Border.all(
                      color: Colors.redAccent.withValues(alpha: 0.3)),
                ),
                child: const Icon(Icons.logout_rounded,
                    color: Colors.redAccent, size: 28),
              ),
              const SizedBox(height: 16),
              const Text(
                'TERMINATE SESSION',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 2,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Are you sure you want to end this admin session?',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.45),
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(ctx),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white70,
                        side: BorderSide(
                            color: Colors.white.withValues(alpha: 0.2)),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('CANCEL',
                          style: TextStyle(letterSpacing: 1.5, fontSize: 12)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.pop(ctx);
                        Navigator.of(context).pushReplacement(
                          PageRouteBuilder(
                            pageBuilder: (_, animation, __) =>
                                const LoginPage(),
                            transitionsBuilder: (_, animation, __, child) =>
                                FadeTransition(
                                    opacity: animation, child: child),
                            transitionDuration:
                                const Duration(milliseconds: 500),
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.redAccent,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('LOGOUT',
                          style: TextStyle(
                              letterSpacing: 1.5,
                              fontWeight: FontWeight.w800,
                              fontSize: 12)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }

  String _formatTime(DateTime dt) {
    final hour = dt.hour;
    final minute = dt.minute.toString().padLeft(2, '0');
    final period = hour >= 12 ? 'PM' : 'AM';
    final displayHour = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
    return '$displayHour:$minute $period';
  }

  String _getTimeAgo(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  Color _getShiftColor(DateTime dt) {
    final hour = dt.hour;
    if (hour >= 6 && hour < 14) return const Color(0xFF00E5FF);
    if (hour >= 14 && hour < 22) return const Color(0xFFFFAB40);
    return const Color(0xFF7C4DFF);
  }

  String _getShiftLabel(DateTime dt) {
    final hour = dt.hour;
    if (hour >= 6 && hour < 14) return 'MORNING';
    if (hour >= 14 && hour < 22) return 'AFTERNOON';
    return 'NIGHT';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF050D18),
      body: StreamBuilder<List<Map<String, dynamic>>>(
        stream: _supabase
            .from('attendance_logs')
            .stream(primaryKey: ['id']).order('arrival_time',
                ascending: false),
        builder: (context, snapshot) {
          final allLogs = snapshot.data ?? [];

          // Compute stats
          final today = DateTime.now();
          _todayCount = allLogs.where((log) {
            final t = DateTime.parse(log['arrival_time'].toString());
            return t.year == today.year &&
                t.month == today.month &&
                t.day == today.day;
          }).length;
          _totalCount = allLogs.length;

          // Filter
          final filteredLogs = allLogs.where((log) {
            final empId = log['employee_id'].toString().toLowerCase();
            final matchesSearch = _searchQuery.isEmpty ||
                empId.contains(_searchQuery.toLowerCase());
            return matchesSearch;
          }).toList();

          return Stack(
            children: [
              // Background
              Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Color(0xFF050D18),
                      Color(0xFF071525),
                      Color(0xFF050D18),
                    ],
                  ),
                ),
              ),
              CustomPaint(
                painter: _GridPainter(),
                size: MediaQuery.of(context).size,
              ),

              // Content
              SafeArea(
                child: Column(
                  children: [
                    _buildAppBar(),
                    _buildStatsRow(snapshot),
                    _buildSearchBar(),
                    Expanded(
                      child: _buildLogsList(snapshot, filteredLogs),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildAppBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 16, 12),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
              color: Colors.white.withValues(alpha: 0.05), width: 1),
        ),
      ),
      child: Row(
        children: [
          // Logo + title
          Row(
            children: [
              AnimatedBuilder(
                animation: _headerRotateController,
                builder: (_, __) => Transform.rotate(
                  angle: _headerRotateController.value * 2 * pi,
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: const Color(0xFF00E5FF).withValues(alpha: 0.4),
                        width: 1,
                      ),
                    ),
                    child: CustomPaint(
                      painter: _DashedCirclePainter(
                        color: const Color(0xFF00E5FF).withValues(alpha: 0.5),
                        radius: 16,
                        dashCount: 8,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Container(
                width: 28,
                height: 28,
                margin: const EdgeInsets.only(left: -22),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF00E5FF).withValues(alpha: 0.1),
                  border: Border.all(
                      color: const Color(0xFF00E5FF).withValues(alpha: 0.5),
                      width: 1),
                ),
                child: const Icon(Icons.face_unlock_rounded,
                    size: 14, color: Color(0xFF00E5FF)),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'BIOID',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 4,
                    ),
                  ),
                  Text(
                    'ATTENDANCE DASHBOARD',
                    style: TextStyle(
                      color: const Color(0xFF00E5FF).withValues(alpha: 0.5),
                      fontSize: 8,
                      letterSpacing: 2.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ],
          ),

          const Spacer(),

          // Live indicator
          AnimatedBuilder(
            animation: _pulseAnimation,
            builder: (_, __) => Row(
              children: [
                Transform.scale(
                  scale: _pulseAnimation.value,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: Color(0xFF00FF88),
                      boxShadow: [
                        BoxShadow(
                            color: Color(0xFF00FF88),
                            blurRadius: 6,
                            spreadRadius: 1),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  'LIVE',
                  style: TextStyle(
                    color: const Color(0xFF00FF88).withValues(alpha: 0.8),
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 2,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(width: 16),

          // Logout button
          GestureDetector(
            onTap: _confirmLogout,
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                color: Colors.redAccent.withValues(alpha: 0.1),
                border: Border.all(
                    color: Colors.redAccent.withValues(alpha: 0.25), width: 1),
              ),
              child: const Icon(Icons.logout_rounded,
                  color: Colors.redAccent, size: 18),
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms);
  }

  Widget _buildStatsRow(AsyncSnapshot snapshot) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Row(
        children: [
          Expanded(
            child: _buildStatCard(
              label: 'TODAY',
              value: snapshot.connectionState == ConnectionState.waiting
                  ? '...'
                  : _todayCount.toString(),
              icon: Icons.today_rounded,
              color: const Color(0xFF00E5FF),
              delay: 100,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _buildStatCard(
              label: 'TOTAL LOGS',
              value: snapshot.connectionState == ConnectionState.waiting
                  ? '...'
                  : _totalCount.toString(),
              icon: Icons.dataset_rounded,
              color: const Color(0xFF7C4DFF),
              delay: 200,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _buildStatCard(
              label: 'STATUS',
              value: 'ONLINE',
              icon: Icons.cloud_done_rounded,
              color: const Color(0xFF00FF88),
              delay: 300,
              isText: true,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatCard({
    required String label,
    required String value,
    required IconData icon,
    required Color color,
    required int delay,
    bool isText = false,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color.withValues(alpha: 0.7)),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: isText ? color : Colors.white,
              fontSize: isText ? 12 : 22,
              fontWeight: FontWeight.w900,
              letterSpacing: isText ? 1.5 : 0,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.3),
              fontSize: 8,
              letterSpacing: 2,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    )
        .animate()
        .fadeIn(delay: delay.ms)
        .slideY(begin: 0.2, end: 0, delay: delay.ms);
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Row(
        children: [
          Expanded(
            child: Container(
              height: 44,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.04),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                    color: Colors.white.withValues(alpha: 0.1), width: 1),
              ),
              child: TextField(
                controller: _searchController,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                onChanged: (v) => setState(() => _searchQuery = v),
                decoration: InputDecoration(
                  hintText: 'Search by employee ID...',
                  hintStyle: TextStyle(
                      color: Colors.white.withValues(alpha: 0.2),
                      fontSize: 12),
                  prefixIcon: Icon(Icons.search_rounded,
                      color: Colors.white.withValues(alpha: 0.3), size: 18),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: 13),
                ),
              ),
            ),
          ),
          if (_searchQuery.isNotEmpty) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () {
                _searchController.clear();
                setState(() => _searchQuery = '');
              },
              child: Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.04),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: Colors.white.withValues(alpha: 0.1), width: 1),
                ),
                child: Icon(Icons.close_rounded,
                    color: Colors.white.withValues(alpha: 0.4), size: 16),
              ),
            ),
          ],
        ],
      ),
    ).animate().fadeIn(delay: 350.ms);
  }

  Widget _buildLogsList(
      AsyncSnapshot snapshot, List<Map<String, dynamic>> logs) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 36,
              height: 36,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: const Color(0xFF00E5FF).withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'LOADING LOGS',
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.3),
                fontSize: 10,
                letterSpacing: 3,
              ),
            ),
          ],
        ),
      );
    }

    if (snapshot.hasError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off_rounded,
                color: Colors.redAccent.withValues(alpha: 0.6), size: 40),
            const SizedBox(height: 12),
            Text(
              'CONNECTION ERROR',
              style: TextStyle(
                color: Colors.redAccent.withValues(alpha: 0.7),
                fontSize: 11,
                letterSpacing: 2,
              ),
            ),
          ],
        ),
      );
    }

    if (logs.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_rounded,
                color: Colors.white.withValues(alpha: 0.15), size: 48),
            const SizedBox(height: 12),
            Text(
              _searchQuery.isEmpty ? 'NO LOGS FOUND' : 'NO RESULTS',
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.25),
                fontSize: 11,
                letterSpacing: 3,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      itemCount: logs.length,
      itemBuilder: (context, index) {
        final log = logs[index];
        final arrivalTime =
            DateTime.parse(log['arrival_time'].toString()).toLocal();
        final shiftColor = _getShiftColor(arrivalTime);

        return _buildLogCard(
          log: log,
          arrivalTime: arrivalTime,
          shiftColor: shiftColor,
          index: index,
        );
      },
    );
  }

  Widget _buildLogCard({
    required Map<String, dynamic> log,
    required DateTime arrivalTime,
    required Color shiftColor,
    required int index,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.07),
          width: 1,
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          children: [
            // Left color bar
            Positioned(
              left: 0,
              top: 0,
              bottom: 0,
              child: Container(
                width: 3,
                decoration: BoxDecoration(
                  color: shiftColor,
                  boxShadow: [
                    BoxShadow(
                      color: shiftColor.withValues(alpha: 0.4),
                      blurRadius: 8,
                      spreadRadius: 0,
                    ),
                  ],
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.fromLTRB(18, 14, 16, 14),
              child: Row(
                children: [
                  // Avatar
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: shiftColor.withValues(alpha: 0.1),
                      border: Border.all(
                          color: shiftColor.withValues(alpha: 0.35), width: 1),
                    ),
                    child: Icon(
                      Icons.badge_outlined,
                      size: 20,
                      color: shiftColor.withValues(alpha: 0.8),
                    ),
                  ),

                  const SizedBox(width: 14),

                  // Main info
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              'EMP-${log['employee_id']}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: shiftColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                    color: shiftColor.withValues(alpha: 0.3),
                                    width: 0.5),
                              ),
                              child: Text(
                                _getShiftLabel(arrivalTime),
                                style: TextStyle(
                                  color: shiftColor,
                                  fontSize: 8,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: 1.5,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 5),
                        Row(
                          children: [
                            Icon(Icons.calendar_today_rounded,
                                size: 10,
                                color: Colors.white.withValues(alpha: 0.3)),
                            const SizedBox(width: 4),
                            Text(
                              _formatDate(arrivalTime),
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.4),
                                fontSize: 11,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Icon(Icons.access_time_rounded,
                                size: 10,
                                color: Colors.white.withValues(alpha: 0.3)),
                            const SizedBox(width: 4),
                            Text(
                              _formatTime(arrivalTime),
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.55),
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  // Time ago
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: const Color(0xFF00FF88).withValues(alpha: 0.1),
                        ),
                        child: const Icon(Icons.how_to_reg_rounded,
                            size: 14, color: Color(0xFF00FF88)),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _getTimeAgo(arrivalTime),
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.25),
                          fontSize: 9,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    )
        .animate()
        .fadeIn(delay: (index * 40).clamp(0, 400).ms)
        .slideY(begin: 0.1, end: 0, delay: (index * 40).clamp(0, 400).ms);
  }
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF00E5FF).withValues(alpha: 0.02)
      ..strokeWidth = 0.5;

    const spacing = 40.0;
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(_) => false;
}

class _DashedCirclePainter extends CustomPainter {
  final Color color;
  final double radius;
  final int dashCount;

  _DashedCirclePainter({
    required this.color,
    required this.radius,
    this.dashCount = 12,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;

    final center = Offset(size.width / 2, size.height / 2);
    final dashAngle = (2 * pi) / dashCount;
    const gapFraction = 0.4;

    for (int i = 0; i < dashCount; i++) {
      final startAngle = i * dashAngle;
      final sweepAngle = dashAngle * (1 - gapFraction);
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        sweepAngle,
        false,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_) => false;
}