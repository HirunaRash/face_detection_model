import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'dart:async';
import 'dart:math';
import 'login_page.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _pulseController;
  late AnimationController _rotateController;
  late AnimationController _scanController;
  late Animation<double> _pulseAnimation;
  late Animation<double> _scanAnimation;

  bool _showScanLine = false;
  bool _scanComplete = false;
  bool _showStatus = false;

  @override
  void initState() {
    super.initState();

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1800),
      vsync: this,
    )..repeat(reverse: true);

    _rotateController = AnimationController(
      duration: const Duration(seconds: 6),
      vsync: this,
    )..repeat();

    _scanController = AnimationController(
      duration: const Duration(milliseconds: 1400),
      vsync: this,
    );

    _pulseAnimation = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _scanAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _scanController, curve: Curves.easeInOut),
    );

    // Sequence of events
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) setState(() => _showScanLine = true);
      _scanController.forward();
    });

    Future.delayed(const Duration(milliseconds: 2800), () {
      if (mounted) setState(() => _scanComplete = true);
    });

    Future.delayed(const Duration(milliseconds: 3100), () {
      if (mounted) setState(() => _showStatus = true);
    });

    Future.delayed(const Duration(milliseconds: 4600), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (_, animation, __) => const LoginPage(),
            transitionsBuilder: (_, animation, __, child) {
              return FadeTransition(
                opacity: CurvedAnimation(
                    parent: animation, curve: Curves.easeInOut),
                child: child,
              );
            },
            transitionDuration: const Duration(milliseconds: 700),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _rotateController.dispose();
    _scanController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF050D18),
              Color(0xFF0A1628),
              Color(0xFF0D2137),
            ],
          ),
        ),
        child: Stack(
          children: [
            // Background grid pattern
            CustomPaint(
              painter: _GridPainter(),
              size: MediaQuery.of(context).size,
            ),

            // Ambient glow orbs
            Positioned(
              top: -80,
              right: -60,
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      const Color(0xFF00E5FF).withValues(alpha: 0.12),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            Positioned(
              bottom: -100,
              left: -80,
              child: Container(
                width: 350,
                height: 350,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      const Color(0xFF7C4DFF).withValues(alpha: 0.1),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),

            // Main content
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Rotating outer ring + biometric scanner
                  SizedBox(
                    width: 200,
                    height: 200,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        // Outer rotating dashed ring
                        AnimatedBuilder(
                          animation: _rotateController,
                          builder: (_, __) => Transform.rotate(
                            angle: _rotateController.value * 2 * pi,
                            child: CustomPaint(
                              painter: _DashedCirclePainter(
                                color: const Color(0xFF00E5FF).withValues(alpha: 0.4),
                                radius: 96,
                              ),
                              size: const Size(200, 200),
                            ),
                          ),
                        ),

                        // Counter-rotating inner ring
                        AnimatedBuilder(
                          animation: _rotateController,
                          builder: (_, __) => Transform.rotate(
                            angle: -_rotateController.value * 2 * pi * 0.7,
                            child: CustomPaint(
                              painter: _DashedCirclePainter(
                                color: const Color(0xFF7C4DFF).withValues(alpha: 0.3),
                                radius: 80,
                                dashCount: 6,
                              ),
                              size: const Size(200, 200),
                            ),
                          ),
                        ),

                        // Pulsing glow ring
                        AnimatedBuilder(
                          animation: _pulseAnimation,
                          builder: (_, __) => Transform.scale(
                            scale: _pulseAnimation.value,
                            child: Container(
                              width: 140,
                              height: 140,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: _scanComplete
                                      ? const Color(0xFF00FF88).withValues(alpha: 0.6)
                                      : const Color(0xFF00E5FF).withValues(alpha: 0.3),
                                  width: 1.5,
                                ),
                                boxShadow: [
                                  BoxShadow(
                                    color: _scanComplete
                                        ? const Color(0xFF00FF88).withValues(alpha: 0.25)
                                        : const Color(0xFF00E5FF).withValues(alpha: 0.15),
                                    blurRadius: 24,
                                    spreadRadius: 4,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),

                        // Face icon container
                        AnimatedBuilder(
                          animation: _pulseAnimation,
                          builder: (_, __) => Container(
                            width: 110,
                            height: 110,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: _scanComplete
                                  ? const Color(0xFF00FF88).withValues(alpha: 0.08)
                                  : const Color(0xFF00E5FF).withValues(alpha: 0.07),
                              border: Border.all(
                                color: _scanComplete
                                    ? const Color(0xFF00FF88).withValues(alpha: 0.5)
                                    : const Color(0xFF00E5FF).withValues(alpha: 0.4),
                                width: 1,
                              ),
                            ),
                            child: ClipOval(
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  Icon(
                                    _scanComplete
                                        ? Icons.verified_user_rounded
                                        : Icons.face_unlock_rounded,
                                    size: 52,
                                    color: _scanComplete
                                        ? const Color(0xFF00FF88)
                                        : const Color(0xFF00E5FF),
                                  ),

                                  // Scan line overlay
                                  if (_showScanLine && !_scanComplete)
                                    AnimatedBuilder(
                                      animation: _scanAnimation,
                                      builder: (_, __) {
                                        return Positioned(
                                          top: _scanAnimation.value * 110 - 1,
                                          left: 0,
                                          right: 0,
                                          child: Container(
                                            height: 2,
                                            decoration: BoxDecoration(
                                              gradient: LinearGradient(
                                                colors: [
                                                  Colors.transparent,
                                                  const Color(0xFF00E5FF).withValues(alpha: 0.9),
                                                  Colors.transparent,
                                                ],
                                              ),
                                              boxShadow: [
                                                BoxShadow(
                                                  color: const Color(0xFF00E5FF).withValues(alpha: 0.6),
                                                  blurRadius: 8,
                                                  spreadRadius: 2,
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  )
                      .animate()
                      .fadeIn(duration: 700.ms, curve: Curves.easeOut)
                      .scale(
                          begin: const Offset(0.5, 0.5),
                          end: const Offset(1.0, 1.0),
                          duration: 800.ms,
                          curve: Curves.easeOutBack),

                  const SizedBox(height: 40),

                  // App name
                  const Text(
                    'BIOID',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 42,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 12,
                      height: 1,
                    ),
                  )
                      .animate()
                      .fadeIn(delay: 400.ms, duration: 600.ms)
                      .slideY(
                          begin: 0.4,
                          end: 0,
                          delay: 400.ms,
                          duration: 600.ms,
                          curve: Curves.easeOutCubic),

                  const SizedBox(height: 6),

                  Text(
                    'BIOMETRIC MANAGEMENT SYSTEM',
                    style: TextStyle(
                      color: const Color(0xFF00E5FF).withValues(alpha: 0.65),
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 3.5,
                    ),
                  )
                      .animate()
                      .fadeIn(delay: 700.ms, duration: 500.ms),

                  const SizedBox(height: 52),

                  // Status area
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 500),
                    child: _showStatus
                        ? _buildStatusRow()
                        : _buildScanningIndicator(),
                  ),

                  const SizedBox(height: 48),

                  // Version tag
                  Text(
                    'v2.4.1  •  SECURE ENCLAVE',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.2),
                      fontSize: 10,
                      letterSpacing: 2,
                    ),
                  ).animate().fadeIn(delay: 900.ms, duration: 400.ms),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScanningIndicator() {
    return Column(
      key: const ValueKey('scanning'),
      children: [
        // Animated dots loader
        Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(
            3,
            (i) => Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF00E5FF),
              ),
            )
                .animate(onPlay: (c) => c.repeat())
                .fadeIn(delay: (i * 200).ms, duration: 300.ms)
                .then()
                .fadeOut(duration: 300.ms),
          ),
        ),
        const SizedBox(height: 12),
        Text(
          'INITIALIZING SYSTEM',
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.35),
            fontSize: 10,
            letterSpacing: 3,
          ),
        ),
      ],
    );
  }

  Widget _buildStatusRow() {
    return Column(
      key: const ValueKey('status'),
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          decoration: BoxDecoration(
            border: Border.all(
                color: const Color(0xFF00FF88).withValues(alpha: 0.4), width: 1),
            borderRadius: BorderRadius.circular(32),
            color: const Color(0xFF00FF88).withValues(alpha: 0.07),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.check_circle_rounded,
                  size: 14, color: Color(0xFF00FF88)),
              const SizedBox(width: 8),
              const Text(
                'IDENTITY VERIFIED',
                style: TextStyle(
                  color: Color(0xFF00FF88),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2.5,
                ),
              ),
            ],
          ),
        )
            .animate()
            .fadeIn(duration: 400.ms)
            .scaleXY(begin: 0.85, end: 1.0, duration: 400.ms, curve: Curves.easeOutBack),
      ],
    );
  }
}

// Custom painter for background grid
class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF00E5FF).withValues(alpha: 0.03)
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

// Custom painter for dashed circle
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
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final center = Offset(size.width / 2, size.height / 2);
    final dashAngle = (2 * pi) / dashCount;
    final gapFraction = 0.4;

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