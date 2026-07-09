import 'dart:async';

import 'package:ai_receptionist_dashboard/staff_api.dart';
import 'package:flutter/material.dart';

class AppColors {
  static const ink = Color(0xFF26323B);
  static const ink2 = Color(0xFFE9EDF1);
  static const panel = Color(0xFFF6F8FA);
  static const panel2 = Color(0xFFE4EAF0);
  static const paper = Color(0xFFFFFFFF);
  static const paper2 = Color(0xFFDDE5EC);
  static const brass = Color(0xFF0D82B8);
  static const ember = Color(0xFFE39A10);
  static const jade = Color(0xFF20B95A);
  static const sky = Color(0xFF8FCFE7);
  static const muted = Color(0xFF6C7782);
  static const line = Color(0xFFC7D1DA);
  static const danger = Color(0xFFC73C36);
}

void main() {
  runApp(StaffDashboardApp(api: StaffApiClient()));
}

class StaffDashboardApp extends StatefulWidget {
  const StaffDashboardApp({
    required this.api,
    this.initialAuthenticated = false,
    this.connectLiveUpdates = true,
    super.key,
  });

  final DashboardApi api;
  final bool initialAuthenticated;
  final bool connectLiveUpdates;

  @override
  State<StaffDashboardApp> createState() => _StaffDashboardAppState();
}

class _StaffDashboardAppState extends State<StaffDashboardApp> {
  bool _authenticated = false;
  bool _loading = false;
  bool _liveConnected = false;
  bool _panelCollapsed = false;
  String? _error;
  DashboardSnapshot? _snapshot;
  DashboardTab _tab = DashboardTab.floor;
  DateTime _selectedDate = DateTime.now();
  TimeOfDay _selectedTime = TimeOfDay.now();
  StreamSubscription<StaffLiveEvent>? _liveSubscription;

  StaffApiClient? get _mutatingApi =>
      widget.api is StaffApiClient ? widget.api as StaffApiClient : null;

  @override
  void initState() {
    super.initState();
    _authenticated = widget.initialAuthenticated;
    if (_authenticated) {
      _refresh();
      _connectLiveUpdates();
    }
  }

  @override
  void dispose() {
    _liveSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ABCD Steakhouse',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'Avenir Next',
        colorScheme: const ColorScheme.light(
          primary: AppColors.brass,
          onPrimary: Colors.white,
          secondary: AppColors.jade,
          onSecondary: Colors.white,
          tertiary: AppColors.sky,
          onTertiary: AppColors.ink,
          surface: AppColors.panel,
          onSurface: AppColors.ink,
          error: AppColors.danger,
        ),
        scaffoldBackgroundColor: AppColors.ink2,
        textTheme: Typography.blackMountainView.apply(
          bodyColor: AppColors.ink,
          displayColor: AppColors.ink,
          fontFamily: 'Avenir Next',
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          color: AppColors.panel,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: AppColors.line),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.paper,
          labelStyle: const TextStyle(color: AppColors.muted),
          prefixIconColor: AppColors.brass,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.line),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: AppColors.brass, width: 1.6),
          ),
          isDense: true,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.brass,
            foregroundColor: Colors.white,
            minimumSize: const Size(44, 44),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
            textStyle: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.brass,
            minimumSize: const Size(44, 44),
            side: const BorderSide(color: AppColors.line),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
        textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
            foregroundColor: AppColors.brass,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
        iconButtonTheme: IconButtonThemeData(
          style: IconButton.styleFrom(
            foregroundColor: AppColors.ink,
            minimumSize: const Size(44, 44),
          ),
        ),
        chipTheme: const ChipThemeData(
          backgroundColor: AppColors.paper,
          selectedColor: AppColors.brass,
          labelStyle: TextStyle(color: AppColors.ink),
          side: BorderSide(color: AppColors.line),
        ),
        tabBarTheme: const TabBarThemeData(
          labelColor: AppColors.brass,
          unselectedLabelColor: AppColors.muted,
          indicatorColor: AppColors.brass,
        ),
        dividerTheme: const DividerThemeData(color: AppColors.line),
        dialogTheme: DialogThemeData(
          backgroundColor: AppColors.panel,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        dataTableTheme: const DataTableThemeData(
          headingTextStyle: TextStyle(
            color: AppColors.brass,
            fontWeight: FontWeight.w800,
          ),
          dataTextStyle: TextStyle(color: AppColors.ink),
          dividerThickness: 0.5,
        ),
      ),
      home: _authenticated
          ? _DashboardHome(
              snapshot: _snapshot,
              loading: _loading,
              error: _error,
              tab: _tab,
              liveConnected: _liveConnected,
              selectedDate: _selectedDate,
              selectedTime: _selectedTime,
              panelCollapsed: _panelCollapsed,
              onTabSelected: (tab) => setState(() => _tab = tab),
              onRefresh: _refresh,
              onDateChanged: _changeDate,
              onTimeChanged: _changeTime,
              onTogglePanel: () =>
                  setState(() => _panelCollapsed = !_panelCollapsed),
              onCreateReservation: _showReservationDialog,
              onCreateWalkIn: _showWalkInDialog,
              onStatusAction: _handleStatusAction,
              onEditReservation: _showEditReservationDialog,
              onFollowupStatus: _updateFollowupStatus,
              onDemoReset: _resetDemo,
              onBackup: _createBackup,
            )
          : _LoginScreen(onLogin: _login),
    );
  }

  Future<void> _login(String password) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.api.login(password);
      if (!mounted) {
        return;
      }
      setState(() => _authenticated = true);
      await _refresh();
      _connectLiveUpdates();
    } on Object catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = _messageFromError(error));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final snapshot = await widget.api.loadDashboard(
        selectedDate: _selectedDate,
        selectedTime: _selectedTime,
      );
      if (!mounted) {
        return;
      }
      setState(() => _snapshot = snapshot);
    } on Object catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = _messageFromError(error));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _connectLiveUpdates() {
    if (!widget.connectLiveUpdates || !_authenticated) {
      return;
    }
    _liveSubscription?.cancel();
    setState(() => _liveConnected = true);
    _liveSubscription = widget.api.liveEvents().listen(
      (_) => _refresh(),
      onError: (_) {
        if (mounted) {
          setState(() => _liveConnected = false);
        }
      },
      onDone: () {
        if (mounted) {
          setState(() => _liveConnected = false);
        }
      },
    );
  }

  Future<void> _changeDate(DateTime date) async {
    setState(() => _selectedDate = date);
    await _refresh();
  }

  Future<void> _changeTime(TimeOfDay time) async {
    setState(() => _selectedTime = time);
    await _refresh();
  }

  Future<void> _showReservationDialog({
    StaffReservation? reservation,
    FloorResource? resource,
  }) async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Reservation editing is connected in live API mode.');
      return;
    }
    final result = await showDialog<ReservationDraft>(
      context: context,
      builder: (context) => ReservationDialog(
        selectedDate: _selectedDate,
        selectedTime: _selectedTime,
        reservation: reservation,
        resource: resource,
      ),
    );
    if (result == null) {
      return;
    }

    await _runMutation(() => client.createReservation(result));
  }

  Future<void> _showEditReservationDialog(StaffReservation reservation) async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Reservation editing is connected in live API mode.');
      return;
    }
    final result = await showDialog<Map<String, Object?>>(
      context: context,
      builder: (context) => EditReservationDialog(reservation: reservation),
    );
    if (result == null) {
      return;
    }

    await _runMutation(() => client.patchReservation(reservation.id, result));
  }

  Future<void> _showWalkInDialog(FloorResource resource) async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Walk-ins are connected in live API mode.');
      return;
    }
    final draft = await showDialog<WalkInDraft>(
      context: context,
      builder: (context) => WalkInDialog(resource: resource),
    );
    if (draft == null) {
      return;
    }
    await _runMutation(() => client.createWalkIn(draft));
  }

  Future<void> _handleStatusAction(
    ReservationAction action,
    StaffReservation reservation,
  ) async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Reservation actions are connected in live API mode.');
      return;
    }

    switch (action) {
      case ReservationAction.arrive:
        await _runMutation(
          () => client.markArrived(reservation.id, reservation.version),
        );
      case ReservationAction.complete:
        final bill = await showDialog<int>(
          context: context,
          builder: (context) =>
              CompleteReservationDialog(reservation: reservation),
        );
        if (bill != null) {
          await _runMutation(
            () => client.completeReservation(
              reservation.id,
              reservation.version,
              bill,
            ),
          );
        }
      case ReservationAction.cancel:
        final confirmed = await _confirm(
          title: 'Cancel reservation',
          body: 'Cancellation SMS will be sent automatically after saving.',
          actionLabel: 'Cancel Reservation',
        );
        if (confirmed) {
          await _runMutation(
            () => client.cancelReservation(reservation.id, reservation.version),
          );
        }
      case ReservationAction.noShow:
        final confirmed = await _confirm(
          title: 'Mark no-show',
          body:
              'This marks the booking as no-show without changing customer details.',
          actionLabel: 'Mark No-show',
        );
        if (confirmed) {
          await _runMutation(
            () => client.markNoShow(reservation.id, reservation.version),
          );
        }
    }
  }

  Future<void> _updateFollowupStatus(
    ManagerFollowup followup,
    String status,
  ) async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Follow-up updates are connected in live API mode.');
      return;
    }
    await _runMutation(
      () => client.updateFollowup(
        followup.id,
        status: status,
        notes: followup.notes,
      ),
    );
  }

  Future<void> _resetDemo() async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Demo reset is connected in live API mode.');
      return;
    }
    final confirmed = await _confirm(
      title: 'Reset demo data',
      body: 'Fictional demo reservations will be recreated.',
      actionLabel: 'Reset Demo Data',
    );
    if (confirmed) {
      await _runMutation(client.resetDemo);
    }
  }

  Future<void> _createBackup() async {
    final client = _mutatingApi;
    if (client == null) {
      _showSnack('Backup is connected in live API mode.');
      return;
    }
    await _runMutation(client.createBackup);
  }

  Future<void> _runMutation(Future<Object?> Function() mutation) async {
    try {
      await mutation();
      await _refresh();
    } on Object catch (error) {
      if (!mounted) {
        return;
      }
      final message = error is StaffApiException && error.isConflict
          ? 'record changed, reload before saving.'
          : _messageFromError(error);
      _showSnack(message);
    }
  }

  Future<bool> _confirm({
    required String title,
    required String body,
    required String actionLabel,
  }) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Close'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(actionLabel),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

enum DashboardTab {
  floor('Floor', Icons.grid_view_rounded),
  reservations('Reservations', Icons.event_note_rounded),
  customers('Customers', Icons.people_alt_rounded),
  followups('Follow-ups', Icons.assignment_late_rounded),
  reports('Reports', Icons.bar_chart_rounded),
  settings('Settings', Icons.settings_rounded);

  const DashboardTab(this.label, this.icon);

  final String label;
  final IconData icon;
}

enum ReservationAction { arrive, complete, cancel, noShow }

class _LoginScreen extends StatefulWidget {
  const _LoginScreen({required this.onLogin});

  final Future<void> Function(String password) onLogin;

  @override
  State<_LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<_LoginScreen> {
  final TextEditingController _password = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF067CB6), Color(0xFF0B8FC8), Color(0xFFE8EEF3)],
          ),
        ),
        child: Stack(
          children: [
            const Positioned.fill(child: _HatchBackground()),
            Align(
              alignment: Alignment.center,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 980),
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final narrow = constraints.maxWidth < 760;
                      final form = _LoginPanel(
                        password: _password,
                        loading: _loading,
                        onSubmit: _submit,
                      );
                      const brand = _LoginBrandPanel();
                      if (narrow) {
                        return Column(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [brand, const SizedBox(height: 18), form],
                        );
                      }
                      return Row(
                        children: [
                          const Expanded(child: brand),
                          const SizedBox(width: 18),
                          Expanded(child: form),
                        ],
                      );
                    },
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    setState(() => _loading = true);
    await widget.onLogin(_password.text);
    if (mounted) {
      setState(() => _loading = false);
    }
  }
}

class _LoginBrandPanel extends StatelessWidget {
  const _LoginBrandPanel();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.paper.withValues(alpha: 0.92),
        border: Border.all(color: Colors.white.withValues(alpha: 0.72)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _BrandMark(size: 58),
            const SizedBox(height: 30),
            Text(
              'ABCD Steakhouse',
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
                height: 0.95,
              ),
            ),
            const SizedBox(height: 14),
            const Text(
              'Live floor operations, reservations, guests, and revenue in one staff console.',
              style: TextStyle(color: AppColors.muted, height: 1.45),
            ),
            const SizedBox(height: 28),
            const Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _LoginSignal(
                  icon: Icons.table_restaurant_rounded,
                  label: '21 resources',
                ),
                _LoginSignal(icon: Icons.bolt_rounded, label: 'Live sync'),
                _LoginSignal(
                  icon: Icons.receipt_long_rounded,
                  label: 'KRW reports',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _LoginPanel extends StatelessWidget {
  const _LoginPanel({
    required this.password,
    required this.loading,
    required this.onSubmit,
  });

  final TextEditingController password;
  final bool loading;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.paper,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.36),
            blurRadius: 42,
            offset: const Offset(0, 22),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Staff access',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: AppColors.ink,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Enter the shared dashboard password to open today\'s service floor.',
              style: TextStyle(color: Color(0xFF5B6472), height: 1.45),
            ),
            const SizedBox(height: 28),
            TextField(
              controller: password,
              obscureText: true,
              style: const TextStyle(color: AppColors.ink),
              decoration: const InputDecoration(
                labelText: 'Staff password',
                prefixIcon: Icon(Icons.lock_outline_rounded),
              ),
              onSubmitted: (_) => onSubmit(),
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: loading ? null : onSubmit,
              icon: loading
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.login_rounded),
              label: const Text('Sign In'),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoginSignal extends StatelessWidget {
  const _LoginSignal({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.panel,
        border: Border.all(color: AppColors.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: AppColors.brass),
            const SizedBox(width: 6),
            Text(label, style: const TextStyle(color: AppColors.ink)),
          ],
        ),
      ),
    );
  }
}

class _BrandMark extends StatelessWidget {
  const _BrandMark({this.size = 38});

  final double size;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.paper,
        border: Border.all(color: AppColors.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: SizedBox.square(
        dimension: size,
        child: Icon(
          Icons.restaurant_menu_rounded,
          color: AppColors.brass,
          size: size * 0.56,
        ),
      ),
    );
  }
}

class _HatchBackground extends StatelessWidget {
  const _HatchBackground();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _HatchPainter());
  }
}

class _HatchPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final linePaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.035)
      ..strokeWidth = 1;
    for (var x = -size.height; x < size.width; x += 28) {
      canvas.drawLine(
        Offset(x, size.height),
        Offset(x + size.height, 0),
        linePaint,
      );
    }
    final glowPaint = Paint()
      ..shader =
          const RadialGradient(
            colors: [Color(0x550072AA), Colors.transparent],
          ).createShader(
            Rect.fromCircle(
              center: Offset(size.width * 0.76, size.height * 0.22),
              radius: size.shortestSide * 0.55,
            ),
          );
    canvas.drawRect(Offset.zero & size, glowPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _DashboardHome extends StatelessWidget {
  const _DashboardHome({
    required this.snapshot,
    required this.loading,
    required this.error,
    required this.tab,
    required this.liveConnected,
    required this.selectedDate,
    required this.selectedTime,
    required this.panelCollapsed,
    required this.onTabSelected,
    required this.onRefresh,
    required this.onDateChanged,
    required this.onTimeChanged,
    required this.onTogglePanel,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
    required this.onFollowupStatus,
    required this.onDemoReset,
    required this.onBackup,
  });

  final DashboardSnapshot? snapshot;
  final bool loading;
  final String? error;
  final DashboardTab tab;
  final bool liveConnected;
  final DateTime selectedDate;
  final TimeOfDay selectedTime;
  final bool panelCollapsed;
  final ValueChanged<DashboardTab> onTabSelected;
  final Future<void> Function() onRefresh;
  final ValueChanged<DateTime> onDateChanged;
  final ValueChanged<TimeOfDay> onTimeChanged;
  final VoidCallback onTogglePanel;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;
  final Future<void> Function(ManagerFollowup followup, String status)
  onFollowupStatus;
  final Future<void> Function() onDemoReset;
  final Future<void> Function() onBackup;

  @override
  Widget build(BuildContext context) {
    final selectedSnapshot = snapshot;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _TopBar(
              tab: tab,
              selectedDate: selectedDate,
              selectedTime: selectedTime,
              liveConnected: liveConnected,
              onTabSelected: onTabSelected,
              onRefresh: onRefresh,
              onDateChanged: onDateChanged,
              onTimeChanged: onTimeChanged,
            ),
            if (!liveConnected)
              Container(
                width: double.infinity,
                color: const Color(0xFF3A2D1B),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: const Row(
                  children: [
                    Icon(Icons.wifi_off_rounded, color: AppColors.brass),
                    SizedBox(width: 8),
                    Text('Internet disconnected. Visible data may be stale.'),
                  ],
                ),
              ),
            if (error != null)
              Container(
                width: double.infinity,
                color: const Color(0xFF44201F),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.error_outline_rounded,
                      color: AppColors.danger,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        error!,
                        style: const TextStyle(color: AppColors.paper),
                      ),
                    ),
                  ],
                ),
              ),
            Expanded(
              child: Stack(
                children: [
                  const Positioned.fill(child: _HatchBackground()),
                  if (selectedSnapshot == null && loading)
                    const Center(child: CircularProgressIndicator())
                  else if (selectedSnapshot == null)
                    _EmptyState(onRefresh: onRefresh)
                  else
                    _DashboardBody(
                      snapshot: selectedSnapshot,
                      tab: tab,
                      selectedDate: selectedDate,
                      selectedTime: selectedTime,
                      panelCollapsed: panelCollapsed,
                      onTogglePanel: onTogglePanel,
                      onCreateReservation: onCreateReservation,
                      onCreateWalkIn: onCreateWalkIn,
                      onStatusAction: onStatusAction,
                      onEditReservation: onEditReservation,
                      onFollowupStatus: onFollowupStatus,
                      onDemoReset: onDemoReset,
                      onBackup: onBackup,
                    ),
                  if (loading && selectedSnapshot != null)
                    const Positioned(
                      top: 12,
                      right: 16,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                        ),
                        child: Padding(
                          padding: EdgeInsets.all(10),
                          child: SizedBox.square(
                            dimension: 22,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.tab,
    required this.selectedDate,
    required this.selectedTime,
    required this.liveConnected,
    required this.onTabSelected,
    required this.onRefresh,
    required this.onDateChanged,
    required this.onTimeChanged,
  });

  final DashboardTab tab;
  final DateTime selectedDate;
  final TimeOfDay selectedTime;
  final bool liveConnected;
  final ValueChanged<DashboardTab> onTabSelected;
  final Future<void> Function() onRefresh;
  final ValueChanged<DateTime> onDateChanged;
  final ValueChanged<TimeOfDay> onTimeChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColors.brass,
        border: Border(bottom: BorderSide(color: Color(0xFF086C9B))),
      ),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 292,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const _BrandMark(size: 38),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'ABCD Steakhouse',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: AppColors.paper,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 0,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              _DateButton(date: selectedDate, onDateChanged: onDateChanged),
              _TimeButton(time: selectedTime, onTimeChanged: onTimeChanged),
              Tooltip(
                message: liveConnected
                    ? 'Live updates connected'
                    : 'Live updates disconnected',
                child: Icon(
                  liveConnected
                      ? Icons.cloud_done_rounded
                      : Icons.cloud_off_rounded,
                  color: liveConnected ? AppColors.jade : AppColors.brass,
                ),
              ),
              IconButton(
                tooltip: 'Refresh',
                color: Colors.white,
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final item in DashboardTab.values)
                  Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: _NavButton(
                      selected: item == tab,
                      item: item,
                      onPressed: () => onTabSelected(item),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.selected,
    required this.item,
    required this.onPressed,
  });

  final bool selected;
  final DashboardTab item;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      style: TextButton.styleFrom(
        foregroundColor: selected ? AppColors.brass : Colors.white,
        backgroundColor: selected
            ? AppColors.paper
            : Colors.white.withValues(alpha: 0.12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        side: BorderSide(
          color: selected
              ? AppColors.paper
              : Colors.white.withValues(alpha: 0.28),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
      ),
      onPressed: onPressed,
      icon: Icon(item.icon, size: 18),
      label: Text(item.label),
    );
  }
}

class _DateButton extends StatelessWidget {
  const _DateButton({required this.date, required this.onDateChanged});

  final DateTime date;
  final ValueChanged<DateTime> onDateChanged;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.paper,
        backgroundColor: AppColors.paper.withValues(alpha: 0.06),
        side: const BorderSide(color: AppColors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      onPressed: () async {
        final picked = await showDatePicker(
          context: context,
          firstDate: DateTime(2024),
          lastDate: DateTime(2030),
          initialDate: date,
        );
        if (picked != null) {
          onDateChanged(picked);
        }
      },
      icon: const Icon(Icons.calendar_month_rounded, size: 18),
      label: Text(formatDate(date)),
    );
  }
}

class _TimeButton extends StatelessWidget {
  const _TimeButton({required this.time, required this.onTimeChanged});

  final TimeOfDay time;
  final ValueChanged<TimeOfDay> onTimeChanged;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      style: OutlinedButton.styleFrom(
        foregroundColor: AppColors.paper,
        backgroundColor: AppColors.paper.withValues(alpha: 0.06),
        side: const BorderSide(color: AppColors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      onPressed: () async {
        final picked = await showTimePicker(
          context: context,
          initialTime: time,
        );
        if (picked != null) {
          onTimeChanged(picked);
        }
      },
      icon: const Icon(Icons.schedule_rounded, size: 18),
      label: Text(formatTimeOfDay(time)),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({
    required this.snapshot,
    required this.tab,
    required this.selectedDate,
    required this.selectedTime,
    required this.panelCollapsed,
    required this.onTogglePanel,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
    required this.onFollowupStatus,
    required this.onDemoReset,
    required this.onBackup,
  });

  final DashboardSnapshot snapshot;
  final DashboardTab tab;
  final DateTime selectedDate;
  final TimeOfDay selectedTime;
  final bool panelCollapsed;
  final VoidCallback onTogglePanel;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;
  final Future<void> Function(ManagerFollowup followup, String status)
  onFollowupStatus;
  final Future<void> Function() onDemoReset;
  final Future<void> Function() onBackup;

  @override
  Widget build(BuildContext context) {
    return switch (tab) {
      DashboardTab.floor => FloorTab(
        snapshot: snapshot,
        report: snapshot.report,
        panelCollapsed: panelCollapsed,
        onTogglePanel: onTogglePanel,
        onCreateReservation: onCreateReservation,
        onCreateWalkIn: onCreateWalkIn,
        onStatusAction: onStatusAction,
        onEditReservation: onEditReservation,
      ),
      DashboardTab.reservations => ReservationsTab(
        reservations: snapshot.reservations,
        selectedDate: selectedDate,
        onStatusAction: onStatusAction,
        onEditReservation: onEditReservation,
      ),
      DashboardTab.customers => CustomersTab(customers: snapshot.customers),
      DashboardTab.followups => FollowupsTab(
        followups: snapshot.followups,
        onStatusChange: onFollowupStatus,
      ),
      DashboardTab.reports => ReportsTab(
        report: snapshot.report,
        reservations: snapshot.reservations,
      ),
      DashboardTab.settings => SettingsTab(
        resources: snapshot.floor.resources,
        onDemoReset: onDemoReset,
        onBackup: onBackup,
      ),
    };
  }
}

class FloorTab extends StatelessWidget {
  const FloorTab({
    required this.snapshot,
    required this.report,
    required this.panelCollapsed,
    required this.onTogglePanel,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
    super.key,
  });

  final DashboardSnapshot snapshot;
  final StaffReport report;
  final bool panelCollapsed;
  final VoidCallback onTogglePanel;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final narrow = constraints.maxWidth < 720;
        final panelWidth = panelCollapsed ? 58.0 : 330.0;
        if (narrow) {
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              SizedBox(
                height: 420,
                child: _ReservationRail(
                  reservations: snapshot.reservations,
                  collapsed: false,
                  onToggle: onTogglePanel,
                  onStatusAction: onStatusAction,
                  onEditReservation: onEditReservation,
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 620,
                child: _FloorMap(
                  resources: snapshot.floor.resources,
                  dailyRevenue: intMetric(report.metrics['revenue_krw']),
                  onCreateReservation: onCreateReservation,
                  onCreateWalkIn: onCreateWalkIn,
                  onStatusAction: onStatusAction,
                  onEditReservation: onEditReservation,
                ),
              ),
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: panelWidth,
              child: _ReservationRail(
                reservations: snapshot.reservations,
                collapsed: panelCollapsed,
                onToggle: onTogglePanel,
                onStatusAction: onStatusAction,
                onEditReservation: onEditReservation,
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
                child: _FloorMap(
                  resources: snapshot.floor.resources,
                  dailyRevenue: intMetric(report.metrics['revenue_krw']),
                  onCreateReservation: onCreateReservation,
                  onCreateWalkIn: onCreateWalkIn,
                  onStatusAction: onStatusAction,
                  onEditReservation: onEditReservation,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ReservationRail extends StatelessWidget {
  const _ReservationRail({
    required this.reservations,
    required this.collapsed,
    required this.onToggle,
    required this.onStatusAction,
    required this.onEditReservation,
  });

  final List<StaffReservation> reservations;
  final bool collapsed;
  final VoidCallback onToggle;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    if (collapsed) {
      return Material(
        color: AppColors.ink2,
        child: DecoratedBox(
          decoration: const BoxDecoration(
            border: Border(right: BorderSide(color: AppColors.line)),
          ),
          child: Column(
            children: [
              IconButton(
                tooltip: 'Expand reservation panel',
                onPressed: onToggle,
                icon: const Icon(Icons.chevron_right_rounded),
              ),
              const SizedBox(height: 8),
              const RotatedBox(
                quarterTurns: 3,
                child: Text(
                  'Reservations',
                  style: TextStyle(
                    fontWeight: FontWeight.w800,
                    color: AppColors.ink,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Material(
      color: AppColors.ink2,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          border: Border(right: BorderSide(color: AppColors.line)),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 14, 10, 12),
              child: Row(
                children: [
                  const Icon(
                    Icons.event_available_rounded,
                    color: AppColors.brass,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Today',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const Spacer(),
                  IconButton(
                    tooltip: 'Collapse reservation panel',
                    onPressed: onToggle,
                    icon: const Icon(Icons.chevron_left_rounded),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: ListView(
                children: [
                  _ReservationGroup(
                    title: 'Upcoming',
                    reservations: reservations
                        .where((item) => item.status == 'confirmed')
                        .toList(),
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                  _ReservationGroup(
                    title: 'Seated',
                    reservations: reservations
                        .where((item) => item.status == 'seated')
                        .toList(),
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                  _ReservationGroup(
                    title: 'Completed',
                    reservations: reservations
                        .where((item) => item.status == 'completed')
                        .toList(),
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                  _ReservationGroup(
                    title: 'Cancelled',
                    reservations: reservations
                        .where((item) => item.status == 'cancelled')
                        .toList(),
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                  _ReservationGroup(
                    title: 'No-show',
                    reservations: reservations
                        .where((item) => item.status == 'no_show')
                        .toList(),
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReservationGroup extends StatelessWidget {
  const _ReservationGroup({
    required this.title,
    required this.reservations,
    required this.onStatusAction,
    required this.onEditReservation,
  });

  final String title;
  final List<StaffReservation> reservations;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      initiallyExpanded: title == 'Upcoming' || title == 'Seated',
      tilePadding: const EdgeInsets.symmetric(horizontal: 14),
      iconColor: AppColors.brass,
      collapsedIconColor: AppColors.muted,
      title: Row(
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(width: 8),
          DecoratedBox(
            decoration: BoxDecoration(
              color: AppColors.brass.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.brass.withValues(alpha: 0.4)),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              child: Text(
                '${reservations.length}',
                style: const TextStyle(
                  color: AppColors.brass,
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
            ),
          ),
        ],
      ),
      children: reservations.isEmpty
          ? const [
              Padding(
                padding: EdgeInsets.fromLTRB(14, 0, 14, 14),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text('None'),
                ),
              ),
            ]
          : [
              for (final reservation in reservations)
                Padding(
                  padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                  child: ReservationTile(
                    reservation: reservation,
                    compact: true,
                    onStatusAction: onStatusAction,
                    onEditReservation: onEditReservation,
                  ),
                ),
            ],
    );
  }
}

class _FloorMap extends StatelessWidget {
  const _FloorMap({
    required this.resources,
    required this.dailyRevenue,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
  });

  final List<FloorResource> resources;
  final int dailyRevenue;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    final positions = <String, Rect>{
      'room_5': const Rect.fromLTWH(0.04, 0.10, 0.13, 0.16),
      'room_4': const Rect.fromLTWH(0.05, 0.42, 0.10, 0.13),
      'room_3': const Rect.fromLTWH(0.05, 0.68, 0.14, 0.17),
      'table_3': const Rect.fromLTWH(0.25, 0.12, 0.09, 0.12),
      'table_4': const Rect.fromLTWH(0.36, 0.12, 0.09, 0.12),
      'table_5': const Rect.fromLTWH(0.72, 0.12, 0.10, 0.12),
      'table_6': const Rect.fromLTWH(0.60, 0.12, 0.10, 0.12),
      'table_7': const Rect.fromLTWH(0.50, 0.28, 0.12, 0.13),
      'table_10': const Rect.fromLTWH(0.73, 0.54, 0.12, 0.13),
      'table_11': const Rect.fromLTWH(0.60, 0.54, 0.12, 0.13),
      'table_12': const Rect.fromLTWH(0.47, 0.54, 0.12, 0.13),
      'table_13': const Rect.fromLTWH(0.34, 0.44, 0.09, 0.12),
      'table_14': const Rect.fromLTWH(0.23, 0.44, 0.09, 0.12),
      'table_15': const Rect.fromLTWH(0.34, 0.70, 0.12, 0.12),
      'table_16': const Rect.fromLTWH(0.22, 0.70, 0.12, 0.12),
      'room_2': const Rect.fromLTWH(0.55, 0.77, 0.12, 0.13),
      'room_1': const Rect.fromLTWH(0.68, 0.77, 0.12, 0.13),
      'table_2': const Rect.fromLTWH(0.86, 0.28, 0.10, 0.12),
      'table_1': const Rect.fromLTWH(0.86, 0.12, 0.10, 0.12),
      'tables_1_2': const Rect.fromLTWH(0.74, 0.26, 0.11, 0.16),
      'rooms_1_2': const Rect.fromLTWH(0.55, 0.66, 0.25, 0.10),
    };

    return Card(
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppColors.paper, AppColors.panel],
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    'Floor',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  _LegendChip(
                    label: 'Empty',
                    color: AppColors.ink2,
                    border: AppColors.line,
                  ),
                  _LegendChip(
                    label: 'Occupied',
                    color: AppColors.jade.withValues(alpha: 0.2),
                    border: AppColors.jade,
                  ),
                  _LegendChip(
                    label: 'Next',
                    color: AppColors.sky.withValues(alpha: 0.2),
                    border: AppColors.sky,
                  ),
                  Chip(
                    avatar: const Icon(
                      Icons.payments_rounded,
                      color: AppColors.brass,
                    ),
                    label: Text(formatKrw(dailyRevenue)),
                  ),
                  OutlinedButton.icon(
                    onPressed: resources.isEmpty
                        ? null
                        : () => onCreateWalkIn(resources.first),
                    icon: const Icon(Icons.chair_alt_rounded),
                    label: const Text('Seat Walk-in'),
                  ),
                  FilledButton.icon(
                    onPressed: () => onCreateReservation(),
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('New Reservation'),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final width = constraints.maxWidth;
                    final height = constraints.maxHeight;
                    return DecoratedBox(
                      decoration: BoxDecoration(
                        color: AppColors.paper,
                        border: Border.all(color: AppColors.line),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Stack(
                        children: [
                          const Positioned.fill(child: _FloorGrid()),
                          for (var i = 0; i < resources.length; i++)
                            _PositionedResourceTile(
                              resource: resources[i],
                              fallbackIndex: i,
                              position: positions[resources[i].id],
                              width: width,
                              height: height,
                              onCreateReservation: onCreateReservation,
                              onCreateWalkIn: onCreateWalkIn,
                              onStatusAction: onStatusAction,
                              onEditReservation: onEditReservation,
                            ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FloorGrid extends StatelessWidget {
  const _FloorGrid();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: _FloorGridPainter());
  }
}

class _FloorGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.line.withValues(alpha: 0.42)
      ..strokeWidth = 1;
    for (var x = 0.0; x < size.width; x += 48) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var y = 0.0; y < size.height; y += 48) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _PositionedResourceTile extends StatelessWidget {
  const _PositionedResourceTile({
    required this.resource,
    required this.fallbackIndex,
    required this.position,
    required this.width,
    required this.height,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
  });

  final FloorResource resource;
  final int fallbackIndex;
  final Rect? position;
  final double width;
  final double height;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    final fallbackColumn = fallbackIndex % 5;
    final fallbackRow = fallbackIndex ~/ 5;
    final rect =
        position ??
        Rect.fromLTWH(
          0.05 + fallbackColumn * 0.18,
          0.08 + fallbackRow * 0.18,
          0.14,
          0.13,
        );
    return Positioned(
      left: rect.left * width,
      top: rect.top * height,
      width: rect.width * width,
      height: rect.height * height,
      child: ResourceTile(
        resource: resource,
        onCreateReservation: onCreateReservation,
        onCreateWalkIn: onCreateWalkIn,
        onStatusAction: onStatusAction,
        onEditReservation: onEditReservation,
      ),
    );
  }
}

class ResourceTile extends StatelessWidget {
  const ResourceTile({
    required this.resource,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
    super.key,
  });

  final FloorResource resource;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    final reservation = resource.currentReservation ?? resource.nextReservation;
    final occupied =
        resource.currentReservation != null || resource.status == 'occupied';
    final hasNext = !occupied && resource.nextReservation != null;
    final background = occupied
        ? AppColors.jade.withValues(alpha: 0.22)
        : hasNext
        ? AppColors.sky.withValues(alpha: 0.22)
        : AppColors.panel2;
    final border = occupied
        ? AppColors.jade
        : hasNext
        ? AppColors.sky
        : AppColors.line;

    return Tooltip(
      message: resource.label,
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => showDialog<void>(
          context: context,
          builder: (context) => ResourceDetailDialog(
            resource: resource,
            onCreateReservation: onCreateReservation,
            onCreateWalkIn: onCreateWalkIn,
            onStatusAction: onStatusAction,
            onEditReservation: onEditReservation,
          ),
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: background,
            border: Border.all(color: border, width: 1.5),
            borderRadius: BorderRadius.circular(
              resource.resourceType == 'room' ? 8 : 28,
            ),
            boxShadow: [
              if (occupied)
                BoxShadow(
                  color: border.withValues(alpha: 0.16),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
            ],
          ),
          child: Center(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: SizedBox(
                width: 112,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      resource.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.ink,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      'Max ${resource.capacity}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 10,
                        color: AppColors.muted,
                      ),
                    ),
                    if (reservation != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        '${formatTime(reservation.reservationStart)} · ${reservation.partySize}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.ink,
                          fontWeight: FontWeight.w700,
                          fontSize: 10,
                        ),
                      ),
                      Text(
                        reservation.customerName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppColors.muted,
                          fontSize: 10,
                        ),
                      ),
                    ],
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

class ResourceDetailDialog extends StatelessWidget {
  const ResourceDetailDialog({
    required this.resource,
    required this.onCreateReservation,
    required this.onCreateWalkIn,
    required this.onStatusAction,
    required this.onEditReservation,
    super.key,
  });

  final FloorResource resource;
  final Future<void> Function({
    StaffReservation? reservation,
    FloorResource? resource,
  })
  onCreateReservation;
  final Future<void> Function(FloorResource resource) onCreateWalkIn;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    final current = resource.currentReservation;
    final next = resource.nextReservation;
    return AlertDialog(
      title: Text(resource.label),
      content: SizedBox(
        width: 460,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Capacity ${resource.capacity}',
              style: const TextStyle(color: Color(0xFF536171)),
            ),
            const SizedBox(height: 16),
            if (current != null)
              ReservationTile(
                reservation: current,
                compact: false,
                onStatusAction: onStatusAction,
                onEditReservation: onEditReservation,
              )
            else
              const Text('Current reservation: empty'),
            const SizedBox(height: 12),
            if (next != null && next.id != current?.id)
              ReservationTile(
                reservation: next,
                compact: false,
                onStatusAction: onStatusAction,
                onEditReservation: onEditReservation,
              )
            else
              const Text('Upcoming reservation: none'),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        OutlinedButton.icon(
          onPressed: () {
            Navigator.pop(context);
            onCreateWalkIn(resource);
          },
          icon: const Icon(Icons.chair_alt_rounded),
          label: const Text('Seat Walk-in'),
        ),
        FilledButton.icon(
          onPressed: () {
            Navigator.pop(context);
            onCreateReservation(resource: resource);
          },
          icon: const Icon(Icons.add_rounded),
          label: const Text('New Reservation'),
        ),
      ],
    );
  }
}

class ReservationTile extends StatelessWidget {
  const ReservationTile({
    required this.reservation,
    required this.compact,
    required this.onStatusAction,
    required this.onEditReservation,
    super.key,
  });

  final StaffReservation reservation;
  final bool compact;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: AppColors.paper,
      child: Padding(
        padding: EdgeInsets.all(compact ? 10 : 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _StatusDot(status: reservation.status),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    reservation.customerName,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.ink,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Text(
                  formatTime(reservation.reservationStart),
                  style: const TextStyle(color: AppColors.brass),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${reservation.partySize} guests · ${reservation.phone}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.muted),
            ),
            if (!compact && reservation.notes != null) ...[
              const SizedBox(height: 6),
              Text(
                reservation.notes!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                Tooltip(
                  message: 'Mark arrived',
                  child: IconButton.filledTonal(
                    onPressed: reservation.status == 'confirmed'
                        ? () => onStatusAction(
                            ReservationAction.arrive,
                            reservation,
                          )
                        : null,
                    icon: const Icon(Icons.login_rounded),
                  ),
                ),
                Tooltip(
                  message: 'Complete',
                  child: IconButton.filledTonal(
                    onPressed: reservation.status == 'seated'
                        ? () => onStatusAction(
                            ReservationAction.complete,
                            reservation,
                          )
                        : null,
                    icon: const Icon(Icons.done_all_rounded),
                  ),
                ),
                Tooltip(
                  message: 'Move or edit notes',
                  child: IconButton.filledTonal(
                    onPressed: () => onEditReservation(reservation),
                    icon: const Icon(Icons.edit_note_rounded),
                  ),
                ),
                Tooltip(
                  message: 'Cancel',
                  child: IconButton.filledTonal(
                    onPressed: reservation.status == 'cancelled'
                        ? null
                        : () => onStatusAction(
                            ReservationAction.cancel,
                            reservation,
                          ),
                    icon: const Icon(Icons.block_rounded),
                  ),
                ),
                Tooltip(
                  message: 'Mark No-show',
                  child: IconButton.filledTonal(
                    onPressed: reservation.status == 'confirmed'
                        ? () => onStatusAction(
                            ReservationAction.noShow,
                            reservation,
                          )
                        : null,
                    icon: const Icon(Icons.person_off_rounded),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class ReservationsTab extends StatefulWidget {
  const ReservationsTab({
    required this.reservations,
    required this.selectedDate,
    required this.onStatusAction,
    required this.onEditReservation,
    super.key,
  });

  final List<StaffReservation> reservations;
  final DateTime selectedDate;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  State<ReservationsTab> createState() => _ReservationsTabState();
}

class _ReservationsTabState extends State<ReservationsTab> {
  String _query = '';
  String _status = 'all';
  CalendarMode _mode = CalendarMode.list;

  @override
  Widget build(BuildContext context) {
    final filtered = widget.reservations.where((reservation) {
      final query = _query.toLowerCase();
      final matchesQuery =
          query.isEmpty ||
          reservation.customerName.toLowerCase().contains(query) ||
          reservation.phone.contains(query) ||
          formatDate(reservation.reservationStart).contains(query);
      final matchesStatus = _status == 'all' || reservation.status == _status;
      return matchesQuery && matchesStatus;
    }).toList();

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Reservation Search',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 340,
                child: TextField(
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.search_rounded),
                    labelText: 'Name, phone, or date',
                  ),
                  onChanged: (value) => setState(() => _query = value),
                ),
              ),
              DropdownButton<String>(
                value: _status,
                items: const [
                  DropdownMenuItem(value: 'all', child: Text('All status')),
                  DropdownMenuItem(
                    value: 'confirmed',
                    child: Text('Confirmed'),
                  ),
                  DropdownMenuItem(value: 'seated', child: Text('Seated')),
                  DropdownMenuItem(
                    value: 'completed',
                    child: Text('Completed'),
                  ),
                  DropdownMenuItem(
                    value: 'cancelled',
                    child: Text('Cancelled'),
                  ),
                  DropdownMenuItem(value: 'no_show', child: Text('No-show')),
                ],
                onChanged: (value) => setState(() => _status = value ?? 'all'),
              ),
              SegmentedButton<CalendarMode>(
                segments: const [
                  ButtonSegment(
                    value: CalendarMode.list,
                    label: Text('List'),
                    icon: Icon(Icons.view_list_rounded),
                  ),
                  ButtonSegment(
                    value: CalendarMode.day,
                    label: Text('Day'),
                    icon: Icon(Icons.calendar_view_day_rounded),
                  ),
                  ButtonSegment(
                    value: CalendarMode.week,
                    label: Text('Week'),
                    icon: Icon(Icons.calendar_view_week_rounded),
                  ),
                ],
                selected: {_mode},
                onSelectionChanged: (value) =>
                    setState(() => _mode = value.single),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: switch (_mode) {
              CalendarMode.list => _ReservationTable(
                reservations: filtered,
                onStatusAction: widget.onStatusAction,
                onEditReservation: widget.onEditReservation,
              ),
              CalendarMode.day => _CalendarBoard(
                reservations: filtered,
                days: 1,
                selectedDate: widget.selectedDate,
                onEditReservation: widget.onEditReservation,
              ),
              CalendarMode.week => _CalendarBoard(
                reservations: filtered,
                days: 7,
                selectedDate: widget.selectedDate,
                onEditReservation: widget.onEditReservation,
              ),
            },
          ),
        ],
      ),
    );
  }
}

enum CalendarMode { list, day, week }

class _ReservationTable extends StatelessWidget {
  const _ReservationTable({
    required this.reservations,
    required this.onStatusAction,
    required this.onEditReservation,
  });

  final List<StaffReservation> reservations;
  final Future<void> Function(
    ReservationAction action,
    StaffReservation reservation,
  )
  onStatusAction;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    if (reservations.isEmpty) {
      return const Center(child: Text('No reservations'));
    }
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        columns: const [
          DataColumn(label: Text('Time')),
          DataColumn(label: Text('Customer')),
          DataColumn(label: Text('Phone')),
          DataColumn(label: Text('Party')),
          DataColumn(label: Text('Status')),
          DataColumn(label: Text('Source')),
          DataColumn(label: Text('Actions')),
        ],
        rows: [
          for (final reservation in reservations)
            DataRow(
              cells: [
                DataCell(
                  Text(
                    '${formatDate(reservation.reservationStart)} ${formatTime(reservation.reservationStart)}',
                  ),
                ),
                DataCell(Text(reservation.customerName)),
                DataCell(Text(reservation.phone)),
                DataCell(Text('${reservation.partySize}')),
                DataCell(Text(labelForStatus(reservation.status))),
                DataCell(Text(labelForSource(reservation.source))),
                DataCell(
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        tooltip: 'Edit',
                        onPressed: () => onEditReservation(reservation),
                        icon: const Icon(Icons.edit_note_rounded),
                      ),
                      IconButton(
                        tooltip: 'Arrived',
                        onPressed: reservation.status == 'confirmed'
                            ? () => onStatusAction(
                                ReservationAction.arrive,
                                reservation,
                              )
                            : null,
                        icon: const Icon(Icons.login_rounded),
                      ),
                      IconButton(
                        tooltip: 'Complete',
                        onPressed: reservation.status == 'seated'
                            ? () => onStatusAction(
                                ReservationAction.complete,
                                reservation,
                              )
                            : null,
                        icon: const Icon(Icons.done_all_rounded),
                      ),
                    ],
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }
}

class _CalendarBoard extends StatelessWidget {
  const _CalendarBoard({
    required this.reservations,
    required this.days,
    required this.selectedDate,
    required this.onEditReservation,
  });

  final List<StaffReservation> reservations;
  final int days;
  final DateTime selectedDate;
  final Future<void> Function(StaffReservation reservation) onEditReservation;

  @override
  Widget build(BuildContext context) {
    final dates = List.generate(
      days,
      (index) => DateTime(
        selectedDate.year,
        selectedDate.month,
        selectedDate.day + index,
      ),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (final date in dates)
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: DragTarget<StaffReservation>(
                    onAcceptWithDetails: (details) =>
                        onEditReservation(details.data),
                    builder: (context, candidate, rejected) => DecoratedBox(
                      decoration: BoxDecoration(
                        color: candidate.isEmpty
                            ? AppColors.ink2
                            : AppColors.jade.withValues(alpha: 0.18),
                        border: Border.all(
                          color: candidate.isEmpty
                              ? AppColors.line
                              : AppColors.jade,
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(10),
                            child: Text(
                              formatDate(date),
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          const Divider(height: 1),
                          Expanded(
                            child: ListView(
                              padding: const EdgeInsets.all(8),
                              children: [
                                for (final reservation in reservations.where(
                                  (item) =>
                                      sameDay(item.reservationStart, date),
                                ))
                                  Padding(
                                    padding: const EdgeInsets.only(bottom: 8),
                                    child: Draggable<StaffReservation>(
                                      data: reservation,
                                      feedback: Material(
                                        elevation: 8,
                                        borderRadius: BorderRadius.circular(8),
                                        child: SizedBox(
                                          width: 220,
                                          child: _CalendarReservationCard(
                                            reservation: reservation,
                                          ),
                                        ),
                                      ),
                                      childWhenDragging: Opacity(
                                        opacity: 0.35,
                                        child: _CalendarReservationCard(
                                          reservation: reservation,
                                        ),
                                      ),
                                      child: _CalendarReservationCard(
                                        reservation: reservation,
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CalendarReservationCard extends StatelessWidget {
  const _CalendarReservationCard({required this.reservation});

  final StaffReservation reservation;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.sky.withValues(alpha: 0.2),
        border: Border.all(color: AppColors.sky),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              formatTime(reservation.reservationStart),
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            Text(
              reservation.customerName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            Text(
              '${reservation.partySize} guests',
              style: const TextStyle(color: AppColors.muted),
            ),
          ],
        ),
      ),
    );
  }
}

class CustomersTab extends StatelessWidget {
  const CustomersTab({required this.customers, super.key});

  final List<CustomerSummary> customers;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Customers',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),
          const TextField(
            decoration: InputDecoration(
              prefixIcon: Icon(Icons.search_rounded),
              labelText: 'Customer search',
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: customers.isEmpty
                ? const Center(child: Text('No customers'))
                : ListView.separated(
                    itemCount: customers.length,
                    separatorBuilder: (context, index) =>
                        const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final customer = customers[index];
                      return Card(
                        child: ListTile(
                          leading: const CircleAvatar(
                            child: Icon(Icons.person_rounded),
                          ),
                          title: Text(customer.name),
                          subtitle: Text(
                            '${customer.phone} · visits ${customer.totalVisits} · upcoming ${customer.upcomingBookings}',
                          ),
                          trailing: Wrap(
                            spacing: 18,
                            children: [
                              _MetricPill(
                                label: 'Cancelled',
                                value: customer.cancellations,
                              ),
                              _MetricPill(
                                label: 'No-show',
                                value: customer.noShows,
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class FollowupsTab extends StatelessWidget {
  const FollowupsTab({
    required this.followups,
    required this.onStatusChange,
    super.key,
  });

  final List<ManagerFollowup> followups;
  final Future<void> Function(ManagerFollowup followup, String status)
  onStatusChange;

  @override
  Widget build(BuildContext context) {
    final groups = {
      'Open': followups.where((item) => item.status == 'open').toList(),
      'Resolved': followups.where((item) => item.status == 'resolved').toList(),
      'Cancelled': followups
          .where((item) => item.status == 'cancelled')
          .toList(),
    };
    return Padding(
      padding: const EdgeInsets.all(16),
      child: DefaultTabController(
        length: groups.length,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Follow-ups',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            TabBar(tabs: [for (final label in groups.keys) Tab(text: label)]),
            Expanded(
              child: TabBarView(
                children: [
                  for (final entry in groups.entries)
                    ListView(
                      padding: const EdgeInsets.only(top: 12),
                      children: entry.value.isEmpty
                          ? const [
                              Center(
                                child: Padding(
                                  padding: EdgeInsets.all(24),
                                  child: Text('No follow-ups'),
                                ),
                              ),
                            ]
                          : [
                              for (final followup in entry.value)
                                Card(
                                  child: ListTile(
                                    leading: const Icon(
                                      Icons.assignment_late_rounded,
                                    ),
                                    title: Text(followup.customerName),
                                    subtitle: Text(
                                      '${followup.reason} · ${followup.phone}',
                                    ),
                                    trailing: Wrap(
                                      spacing: 8,
                                      children: [
                                        IconButton(
                                          tooltip: 'Resolve',
                                          onPressed:
                                              followup.status == 'resolved'
                                              ? null
                                              : () => onStatusChange(
                                                  followup,
                                                  'resolved',
                                                ),
                                          icon: const Icon(
                                            Icons.check_circle_rounded,
                                          ),
                                        ),
                                        IconButton(
                                          tooltip: 'Cancel follow-up',
                                          onPressed:
                                              followup.status == 'cancelled'
                                              ? null
                                              : () => onStatusChange(
                                                  followup,
                                                  'cancelled',
                                                ),
                                          icon: const Icon(
                                            Icons.cancel_rounded,
                                          ),
                                        ),
                                      ],
                                    ),
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
    );
  }
}

class ReportsTab extends StatelessWidget {
  const ReportsTab({
    required this.report,
    required this.reservations,
    super.key,
  });

  final StaffReport report;
  final List<StaffReservation> reservations;

  @override
  Widget build(BuildContext context) {
    final revenue = intMetric(report.metrics['revenue_krw']);
    final bookings = intMetric(report.metrics['bookings']);
    final completed = intMetric(report.metrics['completed_visits']);
    final noShows = intMetric(report.metrics['no_shows']);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Reports',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              _ReportCard(
                label: 'Bookings',
                value: '$bookings',
                icon: Icons.event_available_rounded,
              ),
              _ReportCard(
                label: 'Completed',
                value: '$completed',
                icon: Icons.done_all_rounded,
              ),
              _ReportCard(
                label: 'No-show',
                value: '$noShows',
                icon: Icons.person_off_rounded,
              ),
              _ReportCard(
                label: 'Revenue',
                value: formatKrw(revenue),
                icon: Icons.payments_rounded,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Daily Revenue',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Expanded(
                      child: ListView(
                        children: [
                          _SourceBar(
                            label: 'AI calls',
                            value: reservations
                                .where((item) => item.source == 'ai_call')
                                .length,
                            total: reservations.length,
                          ),
                          _SourceBar(
                            label: 'Staff manual',
                            value: reservations
                                .where((item) => item.source == 'staff_manual')
                                .length,
                            total: reservations.length,
                          ),
                          _SourceBar(
                            label: 'Walk-ins',
                            value: reservations
                                .where((item) => item.source == 'walk_in')
                                .length,
                            total: reservations.length,
                          ),
                          _SourceBar(
                            label: 'Completed',
                            value: completed,
                            total: bookings,
                          ),
                          _SourceBar(
                            label: 'No-show',
                            value: noShows,
                            total: bookings,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class SettingsTab extends StatefulWidget {
  const SettingsTab({
    required this.resources,
    required this.onDemoReset,
    required this.onBackup,
    super.key,
  });

  final List<FloorResource> resources;
  final Future<void> Function() onDemoReset;
  final Future<void> Function() onBackup;

  @override
  State<SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends State<SettingsTab> {
  double _duration = 100;
  TimeOfDay _open = const TimeOfDay(hour: 11, minute: 0);
  TimeOfDay _close = const TimeOfDay(hour: 21, minute: 0);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          Text(
            'Settings',
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Restaurant Hours',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      OutlinedButton.icon(
                        onPressed: () async {
                          final picked = await showTimePicker(
                            context: context,
                            initialTime: _open,
                          );
                          if (picked != null) {
                            setState(() => _open = picked);
                          }
                        },
                        icon: const Icon(Icons.wb_sunny_rounded),
                        label: Text(formatTimeOfDay(_open)),
                      ),
                      OutlinedButton.icon(
                        onPressed: () async {
                          final picked = await showTimePicker(
                            context: context,
                            initialTime: _close,
                          );
                          if (picked != null) {
                            setState(() => _close = picked);
                          }
                        },
                        icon: const Icon(Icons.nightlight_round),
                        label: Text(formatTimeOfDay(_close)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text('Reservation Duration: ${_duration.round()} minutes'),
                  Slider(
                    value: _duration,
                    min: 60,
                    max: 150,
                    divisions: 9,
                    label: '${_duration.round()}',
                    onChanged: (value) => setState(() => _duration = value),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Tables And Rooms',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final resource in widget.resources)
                        Chip(
                          avatar: Icon(
                            resource.resourceType == 'room'
                                ? Icons.meeting_room_rounded
                                : Icons.table_bar_rounded,
                          ),
                          label: Text(
                            '${resource.label} · ${resource.capacity}',
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  FilledButton.icon(
                    onPressed: widget.onDemoReset,
                    icon: const Icon(Icons.restart_alt_rounded),
                    label: const Text('Reset Demo Data'),
                  ),
                  OutlinedButton.icon(
                    onPressed: widget.onBackup,
                    icon: const Icon(Icons.backup_rounded),
                    label: const Text('Back Up Database'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ReservationDialog extends StatefulWidget {
  const ReservationDialog({
    required this.selectedDate,
    required this.selectedTime,
    required this.reservation,
    required this.resource,
    super.key,
  });

  final DateTime selectedDate;
  final TimeOfDay selectedTime;
  final StaffReservation? reservation;
  final FloorResource? resource;

  @override
  State<ReservationDialog> createState() => _ReservationDialogState();
}

class _ReservationDialogState extends State<ReservationDialog> {
  late final TextEditingController _name;
  late final TextEditingController _phone;
  late final TextEditingController _party;
  late final TextEditingController _notes;
  late final TextEditingController _allergies;
  late DateTime _date;
  late TimeOfDay _time;
  String _seating = 'no_preference';

  @override
  void initState() {
    super.initState();
    final reservation = widget.reservation;
    _name = TextEditingController(text: reservation?.customerName ?? '');
    _phone = TextEditingController(text: reservation?.phone ?? '');
    _party = TextEditingController(text: '${reservation?.partySize ?? 2}');
    _notes = TextEditingController(text: reservation?.notes ?? '');
    _allergies = TextEditingController(text: reservation?.allergyNotes ?? '');
    _date = reservation?.reservationStart ?? widget.selectedDate;
    _time = reservation != null
        ? TimeOfDay(
            hour: reservation.reservationStart.hour,
            minute: reservation.reservationStart.minute,
          )
        : widget.selectedTime;
    _seating =
        reservation?.seatingPreference ??
        (widget.resource?.resourceType == 'room'
            ? 'private_room'
            : 'no_preference');
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _party.dispose();
    _notes.dispose();
    _allergies.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New Reservation'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Customer name'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _phone,
                decoration: const InputDecoration(labelText: 'Phone'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _party,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Party size'),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: context,
                          firstDate: DateTime(2024),
                          lastDate: DateTime(2030),
                          initialDate: _date,
                        );
                        if (picked != null) {
                          setState(() => _date = picked);
                        }
                      },
                      icon: const Icon(Icons.calendar_month_rounded),
                      label: Text(formatDate(_date)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () async {
                        final picked = await showTimePicker(
                          context: context,
                          initialTime: _time,
                        );
                        if (picked != null) {
                          setState(() => _time = picked);
                        }
                      },
                      icon: const Icon(Icons.schedule_rounded),
                      label: Text(formatTimeOfDay(_time)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _seating,
                decoration: const InputDecoration(
                  labelText: 'Seating preference',
                ),
                items: const [
                  DropdownMenuItem(
                    value: 'no_preference',
                    child: Text('No preference'),
                  ),
                  DropdownMenuItem(value: 'table', child: Text('Table')),
                  DropdownMenuItem(
                    value: 'private_room',
                    child: Text('Private room'),
                  ),
                ],
                onChanged: (value) =>
                    setState(() => _seating = value ?? 'no_preference'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _notes,
                decoration: const InputDecoration(labelText: 'Notes'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _allergies,
                decoration: const InputDecoration(labelText: 'Allergies'),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: () {
            final start = DateTime(
              _date.year,
              _date.month,
              _date.day,
              _time.hour,
              _time.minute,
            );
            Navigator.pop(
              context,
              ReservationDraft(
                customerName: _name.text,
                phone: _phone.text,
                partySize: int.tryParse(_party.text) ?? 1,
                reservationStart: start,
                seatingPreference: _seating,
                resourceId: widget.resource?.id,
                notes: nullIfBlank(_notes.text),
                allergyNotes: nullIfBlank(_allergies.text),
              ),
            );
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class EditReservationDialog extends StatefulWidget {
  const EditReservationDialog({required this.reservation, super.key});

  final StaffReservation reservation;

  @override
  State<EditReservationDialog> createState() => _EditReservationDialogState();
}

class _EditReservationDialogState extends State<EditReservationDialog> {
  late final TextEditingController _resource;
  late final TextEditingController _notes;
  late final TextEditingController _party;

  @override
  void initState() {
    super.initState();
    _resource = TextEditingController(
      text: widget.reservation.resourceIds.firstOrNull ?? '',
    );
    _notes = TextEditingController(text: widget.reservation.notes ?? '');
    _party = TextEditingController(text: '${widget.reservation.partySize}');
  }

  @override
  void dispose() {
    _resource.dispose();
    _notes.dispose();
    _party.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Reservation'),
      content: SizedBox(
        width: 430,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _resource,
              decoration: const InputDecoration(labelText: 'Table or room ID'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _party,
              decoration: const InputDecoration(labelText: 'Party size'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _notes,
              decoration: const InputDecoration(labelText: 'Internal note'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: () {
            Navigator.pop(context, {
              'expected_version': widget.reservation.version,
              'resource_id': nullIfBlank(_resource.text),
              'party_size': int.tryParse(_party.text),
              'notes': nullIfBlank(_notes.text) ?? '',
            });
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class WalkInDialog extends StatefulWidget {
  const WalkInDialog({required this.resource, super.key});

  final FloorResource resource;

  @override
  State<WalkInDialog> createState() => _WalkInDialogState();
}

class _WalkInDialogState extends State<WalkInDialog> {
  final TextEditingController _party = TextEditingController(text: '2');
  final TextEditingController _notes = TextEditingController();

  @override
  void dispose() {
    _party.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Seat Walk-in'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            widget.resource.label,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _party,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Party size'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _notes,
            decoration: const InputDecoration(labelText: 'Notes'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(
            context,
            WalkInDraft(
              partySize: int.tryParse(_party.text) ?? 1,
              resourceId: widget.resource.id,
              seatedAt: DateTime.now(),
              notes: nullIfBlank(_notes.text),
            ),
          ),
          child: const Text('Seat'),
        ),
      ],
    );
  }
}

class CompleteReservationDialog extends StatefulWidget {
  const CompleteReservationDialog({required this.reservation, super.key});

  final StaffReservation reservation;

  @override
  State<CompleteReservationDialog> createState() =>
      _CompleteReservationDialogState();
}

class _CompleteReservationDialogState extends State<CompleteReservationDialog> {
  final TextEditingController _bill = TextEditingController();

  @override
  void dispose() {
    _bill.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Complete'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.reservation.customerName,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _bill,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'Final bill KRW'),
          ),
          if (widget.reservation.privateRoomMinimumSpendKrw != null) ...[
            const SizedBox(height: 10),
            Text(
              'Private-room minimum ${formatKrw(widget.reservation.privateRoomMinimumSpendKrw!)}',
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
        FilledButton(
          onPressed: () =>
              Navigator.pop(context, int.tryParse(_bill.text) ?? 0),
          child: const Text('Complete'),
        ),
      ],
    );
  }
}

class _LegendChip extends StatelessWidget {
  const _LegendChip({
    required this.label,
    required this.color,
    required this.border,
  });

  final String label;
  final Color color;
  final Color border;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: color,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        child: Text(label, style: const TextStyle(fontSize: 12)),
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'confirmed' => AppColors.sky,
      'seated' => AppColors.jade,
      'completed' => AppColors.muted,
      'cancelled' => AppColors.danger,
      'no_show' => AppColors.brass,
      _ => AppColors.muted,
    };
    return Container(
      width: 12,
      height: 12,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text('$value', style: const TextStyle(fontWeight: FontWeight.w800)),
        Text(
          label,
          style: const TextStyle(color: Color(0xFF536171), fontSize: 12),
        ),
      ],
    );
  }
}

class _ReportCard extends StatelessWidget {
  const _ReportCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 220,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: const Color(0xFFE0F2FE),
                child: Icon(icon),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      value,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      label,
                      style: const TextStyle(color: Color(0xFF536171)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SourceBar extends StatelessWidget {
  const _SourceBar({
    required this.label,
    required this.value,
    required this.total,
  });

  final String label;
  final int value;
  final int total;

  @override
  Widget build(BuildContext context) {
    final ratio = total <= 0 ? 0.0 : value / total;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text('$value'),
            ],
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(
            value: ratio.clamp(0, 1),
            minHeight: 10,
            borderRadius: BorderRadius.circular(8),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onRefresh});

  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_rounded, size: 48),
          const SizedBox(height: 12),
          const Text('No dashboard data loaded'),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Refresh'),
          ),
        ],
      ),
    );
  }
}

String formatDate(DateTime date) {
  return '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';
}

String formatTime(DateTime date) {
  return '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}

String formatTimeOfDay(TimeOfDay time) {
  return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
}

String formatKrw(int value) {
  final raw = value.toString();
  final buffer = StringBuffer();
  for (var i = 0; i < raw.length; i++) {
    if (i > 0 && (raw.length - i) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(raw[i]);
  }
  return 'KRW $buffer';
}

String labelForStatus(String status) {
  return switch (status) {
    'confirmed' => 'Confirmed',
    'seated' => 'Seated',
    'completed' => 'Completed',
    'cancelled' => 'Cancelled',
    'no_show' => 'No-show',
    _ => status,
  };
}

String labelForSource(String source) {
  return switch (source) {
    'ai_call' => 'AI call',
    'staff_manual' => 'Staff manual',
    'walk_in' => 'Walk-in',
    _ => source,
  };
}

int intMetric(Object? value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.round();
  }
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

bool sameDay(DateTime left, DateTime right) {
  return left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;
}

String? nullIfBlank(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}

String _messageFromError(Object error) {
  if (error is StaffApiException) {
    return error.message;
  }
  return error.toString();
}
