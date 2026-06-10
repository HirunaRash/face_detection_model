import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'dart:math';
import 'dashboard_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> with TickerProviderStateMixin {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _usernameFocus = FocusNode();
  final _passwordFocus = FocusNode();
  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _usernameFocused = false;
  bool _passwordFocused = false;
  final _supabase = Supabase.instance.client;

  late AnimationController _bgRotateController;

  @override
  void initState() {
    super.initState();
    _bgRotateController = AnimationController(
      duration: const Duration(seconds: 20),
      vsync: this,
    )..repeat();

    _usernameFocus.addListener(() {
      setState(() => _usernameFocused = _usernameFocus.hasFocus);
    });
    _passwordFocus.addListener(() {
      setState(() => _passwordFocused = _passwordFocus.hasFocus);
    });
  }

  @override
  void dispose() {
    _bgRotateController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _usernameFocus.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (_usernameController.text.trim().isEmpty ||
        _passwordController.text.isEmpty) {
      _showSnackBar('Please fill in all fields', isError: true);
      return;
    }

    setState(() => _isLoading = true);
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    try {
      final response = await _supabase
          .from('app_login_credentials')
          .select()
          .eq('username', username)
          .eq('password', password)
          .maybeSingle();

      if (!mounted) return;

      if (response != null) {
        _showSnackBar('Access granted', isError: false);
        await Future.delayed(const Duration(milliseconds: 600));
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (_, animation, __) => const DashboardPage(),
            transitionsBuilder: (_, animation, __, child) {
              return FadeTransition(
                opacity: CurvedAnimation(
                    parent: animation, curve: Curves.easeInOut),
                child: child,
              );
            },
            transitionDuration: const Duration(milliseconds: 600),
          ),
        );
      } else {
        _showSnackBar('Invalid credentials — access denied', isError: true);
      }
    } catch (e) {
      if (!mounted) return;
      _showSnackBar('Connection error: $e', isError: true);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showSnackBar(String message, {required bool isError}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.check_circle_outline,
              color: Colors.white,
              size: 18,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
        backgroundColor:
            isError ? const Color(0xFFB00020) : const Color(0xFF00C853),
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        duration: const Duration(seconds: 3),
      ),
    );
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
            // Background grid
            CustomPaint(
              painter: _GridPainter(),
              size: MediaQuery.of(context).size,
            ),

            // Ambient glow top-right
            Positioned(
              top: -120,
              right: -80,
              child: Container(
                width: 400,
                height: 400,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      const Color(0xFF00E5FF).withValues(alpha: 0.09),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),

            // Rotating decorative ring bottom-left
            Positioned(
              bottom: -140,
              left: -100,
              child: AnimatedBuilder(
                animation: _bgRotateController,
                builder: (_, __) => Transform.rotate(
                  angle: _bgRotateController.value * 2 * pi,
                  child: Container(
                    width: 320,
                    height: 320,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: const Color(0xFF7C4DFF).withValues(alpha: 0.08),
                        width: 1,
                      ),
                    ),
                    child: CustomPaint(
                      painter: _DashedCirclePainter(
                        color: const Color(0xFF7C4DFF).withValues(alpha: 0.12),
                        radius: 158,
                        dashCount: 8,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // Main scrollable content
            SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 24.0, vertical: 32),
                  child: Column(
                    children: [
                      // Header area
                      _buildHeader(),

                      const SizedBox(height: 40),

                      // Card
                      _buildLoginCard(),

                      const SizedBox(height: 32),

                      // Footer
                      _buildFooter(),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        // Icon with corner brackets
        Stack(
          alignment: Alignment.center,
          children: [
            // Corner brackets decoration
            ..._buildCornerBrackets(size: 80, color: const Color(0xFF00E5FF)),

            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF00E5FF).withValues(alpha: 0.08),
                border: Border.all(
                  color: const Color(0xFF00E5FF).withValues(alpha: 0.35),
                  width: 1.5,
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF00E5FF).withValues(alpha: 0.2),
                    blurRadius: 20,
                    spreadRadius: 4,
                  ),
                ],
              ),
              child: const Icon(
                Icons.security_rounded,
                size: 34,
                color: Color(0xFF00E5FF),
              ),
            ),
          ],
        )
            .animate()
            .fadeIn(duration: 600.ms)
            .scale(
                begin: const Offset(0.7, 0.7),
                end: const Offset(1.0, 1.0),
                duration: 700.ms,
                curve: Curves.easeOutBack),

        const SizedBox(height: 20),

        const Text(
          'ADMIN ACCESS',
          style: TextStyle(
            color: Colors.white,
            fontSize: 26,
            fontWeight: FontWeight.w900,
            letterSpacing: 6,
          ),
        ).animate().fadeIn(delay: 150.ms).slideY(begin: 0.3, end: 0),

        const SizedBox(height: 6),

        Text(
          'BIOID MANAGEMENT SYSTEM',
          style: TextStyle(
            color: const Color(0xFF00E5FF).withValues(alpha: 0.55),
            fontSize: 10,
            letterSpacing: 3.5,
            fontWeight: FontWeight.w600,
          ),
        ).animate().fadeIn(delay: 250.ms),

        const SizedBox(height: 16),

        // Status bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            border: Border.all(
                color: const Color(0xFF00E5FF).withValues(alpha: 0.2), width: 1),
            borderRadius: BorderRadius.circular(20),
            color: const Color(0xFF00E5FF).withValues(alpha: 0.04),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
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
              )
                  .animate(onPlay: (c) => c.repeat(reverse: true))
                  .fadeIn(duration: 600.ms)
                  .then()
                  .fadeOut(duration: 600.ms),
              const SizedBox(width: 8),
              Text(
                'SECURE CONNECTION ESTABLISHED',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.4),
                  fontSize: 9,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ).animate().fadeIn(delay: 350.ms),
      ],
    );
  }

  Widget _buildLoginCard() {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.08),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 32,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section label
          Text(
            'CREDENTIALS',
            style: TextStyle(
              color: const Color(0xFF00E5FF).withValues(alpha: 0.5),
              fontSize: 10,
              letterSpacing: 3,
              fontWeight: FontWeight.w700,
            ),
          ).animate().fadeIn(delay: 400.ms),

          const SizedBox(height: 20),

          // Username field
          _buildTextField(
            controller: _usernameController,
            focusNode: _usernameFocus,
            isFocused: _usernameFocused,
            label: 'Username',
            hint: 'Enter your username',
            prefixIcon: Icons.person_outline_rounded,
            delay: 450,
          ),

          const SizedBox(height: 16),

          // Password field
          _buildTextField(
            controller: _passwordController,
            focusNode: _passwordFocus,
            isFocused: _passwordFocused,
            label: 'Password',
            hint: '••••••••',
            prefixIcon: Icons.lock_outline_rounded,
            isPassword: true,
            delay: 550,
          ),

          const SizedBox(height: 28),

          // Divider
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 1,
                  color: Colors.white.withValues(alpha: 0.06),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                child: Text(
                  'VERIFY',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.2),
                    fontSize: 9,
                    letterSpacing: 3,
                  ),
                ),
              ),
              Expanded(
                child: Container(
                  height: 1,
                  color: Colors.white.withValues(alpha: 0.06),
                ),
              ),
            ],
          ).animate().fadeIn(delay: 600.ms),

          const SizedBox(height: 24),

          // Login button
          _buildLoginButton(),
        ],
      ),
    ).animate().fadeIn(delay: 300.ms).slideY(begin: 0.2, end: 0);
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required FocusNode focusNode,
    required bool isFocused,
    required String label,
    required String hint,
    required IconData prefixIcon,
    bool isPassword = false,
    required int delay,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: TextStyle(
            color: isFocused
                ? const Color(0xFF00E5FF)
                : Colors.white.withValues(alpha: 0.35),
            fontSize: 9,
            letterSpacing: 2.5,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isFocused
                  ? const Color(0xFF00E5FF).withValues(alpha: 0.6)
                  : Colors.white.withValues(alpha: 0.1),
              width: isFocused ? 1.5 : 1,
            ),
            color: isFocused
                ? const Color(0xFF00E5FF).withValues(alpha: 0.05)
                : Colors.white.withValues(alpha: 0.03),
            boxShadow: isFocused
                ? [
                    BoxShadow(
                      color: const Color(0xFF00E5FF).withValues(alpha: 0.1),
                      blurRadius: 12,
                      spreadRadius: 0,
                    ),
                  ]
                : [],
          ),
          child: TextField(
            controller: controller,
            focusNode: focusNode,
            obscureText: isPassword ? _obscurePassword : false,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 15,
              fontWeight: FontWeight.w400,
            ),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(
                color: Colors.white.withValues(alpha: 0.2),
                fontSize: 14,
              ),
              prefixIcon: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Icon(
                  prefixIcon,
                  color: isFocused
                      ? const Color(0xFF00E5FF)
                      : Colors.white.withValues(alpha: 0.3),
                  size: 20,
                ),
              ),
              prefixIconConstraints: const BoxConstraints(
                minWidth: 48,
                minHeight: 48,
              ),
              suffixIcon: isPassword
                  ? IconButton(
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                        color: Colors.white.withValues(alpha: 0.3),
                        size: 18,
                      ),
                      onPressed: () {
                        setState(() => _obscurePassword = !_obscurePassword);
                      },
                    )
                  : null,
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 16),
            ),
          ),
        ),
      ],
    ).animate().fadeIn(delay: delay.ms).slideX(
        begin: isPassword ? 0.05 : -0.05, end: 0, delay: delay.ms);
  }

  Widget _buildLoginButton() {
    return SizedBox(
      width: double.infinity,
      height: 54,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          boxShadow: _isLoading
              ? []
              : [
                  BoxShadow(
                    color: const Color(0xFF00E5FF).withValues(alpha: 0.3),
                    blurRadius: 20,
                    offset: const Offset(0, 6),
                  ),
                ],
        ),
        child: ElevatedButton(
          onPressed: _isLoading ? null : _login,
          style: ElevatedButton.styleFrom(
            backgroundColor: _isLoading
                ? const Color(0xFF00E5FF).withValues(alpha: 0.4)
                : const Color(0xFF00E5FF),
            foregroundColor: const Color(0xFF050D18),
            disabledBackgroundColor:
                const Color(0xFF00E5FF).withValues(alpha: 0.4),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: _isLoading
              ? Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: const Color(0xFF050D18).withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      'VERIFYING...',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 2,
                        color: const Color(0xFF050D18).withValues(alpha: 0.7),
                      ),
                    ),
                  ],
                )
              : const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.shield_rounded, size: 18),
                    SizedBox(width: 10),
                    Text(
                      'AUTHENTICATE',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 2.5,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    ).animate().fadeIn(delay: 650.ms).scaleXY(
        begin: 0.92, end: 1.0, delay: 650.ms, curve: Curves.easeOutBack);
  }

  Widget _buildFooter() {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildFooterChip(Icons.lock_rounded, 'ENCRYPTED'),
            const SizedBox(width: 12),
            _buildFooterChip(Icons.verified_user_rounded, 'SECURE'),
            const SizedBox(width: 12),
            _buildFooterChip(Icons.shield_rounded, 'PROTECTED'),
          ],
        ),
        const SizedBox(height: 20),
        Text(
          '© 2025 BIOID SYSTEM  •  ADMIN PORTAL',
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.15),
            fontSize: 9,
            letterSpacing: 2,
          ),
        ),
      ],
    ).animate().fadeIn(delay: 750.ms);
  }

  Widget _buildFooterChip(IconData icon, String label) {
    return Row(
      children: [
        Icon(icon, size: 10, color: Colors.white.withValues(alpha: 0.25)),
        const SizedBox(width: 5),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.25),
            fontSize: 9,
            letterSpacing: 1.5,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  List<Widget> _buildCornerBrackets(
      {required double size, required Color color}) {
    const bracketSize = 12.0;
    const bracketThickness = 2.0;
    final bracketColor = color.withValues(alpha: 0.5);
    final offset = (size / 2) + 8;

    return [
      // Top-left
      Positioned(
        top: -offset + 6,
        left: -offset + 6,
        child: CustomPaint(
          painter: _CornerBracketPainter(
              color: bracketColor,
              size: bracketSize,
              thickness: bracketThickness,
              corner: 'tl'),
          size: Size(bracketSize, bracketSize),
        ),
      ),
      // Top-right
      Positioned(
        top: -offset + 6,
        right: -offset + 6,
        child: CustomPaint(
          painter: _CornerBracketPainter(
              color: bracketColor,
              size: bracketSize,
              thickness: bracketThickness,
              corner: 'tr'),
          size: Size(bracketSize, bracketSize),
        ),
      ),
      // Bottom-left
      Positioned(
        bottom: -offset + 6,
        left: -offset + 6,
        child: CustomPaint(
          painter: _CornerBracketPainter(
              color: bracketColor,
              size: bracketSize,
              thickness: bracketThickness,
              corner: 'bl'),
          size: Size(bracketSize, bracketSize),
        ),
      ),
      // Bottom-right
      Positioned(
        bottom: -offset + 6,
        right: -offset + 6,
        child: CustomPaint(
          painter: _CornerBracketPainter(
              color: bracketColor,
              size: bracketSize,
              thickness: bracketThickness,
              corner: 'br'),
          size: Size(bracketSize, bracketSize),
        ),
      ),
    ];
  }
}

class _CornerBracketPainter extends CustomPainter {
  final Color color;
  final double size;
  final double thickness;
  final String corner;

  _CornerBracketPainter(
      {required this.color,
      required this.size,
      required this.thickness,
      required this.corner});

  @override
  void paint(Canvas canvas, Size canvasSize) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = thickness
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.square;

    final path = Path();
    switch (corner) {
      case 'tl':
        path.moveTo(size, 0);
        path.lineTo(0, 0);
        path.lineTo(0, size);
        break;
      case 'tr':
        path.moveTo(0, 0);
        path.lineTo(size, 0);
        path.lineTo(size, size);
        break;
      case 'bl':
        path.moveTo(0, 0);
        path.lineTo(0, size);
        path.lineTo(size, size);
        break;
      case 'br':
        path.moveTo(0, size);
        path.lineTo(size, size);
        path.lineTo(size, 0);
        break;
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_) => false;
}

class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF00E5FF).withValues(alpha: 0.025)
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
      ..strokeWidth = 1.5
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