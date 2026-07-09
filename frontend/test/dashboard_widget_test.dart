import 'package:ai_receptionist_dashboard/main.dart';
import 'package:ai_receptionist_dashboard/staff_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeDashboardApi implements DashboardApi {
  @override
  Future<void> login(String password) async {}

  @override
  Future<DashboardSnapshot> loadDashboard({
    required DateTime selectedDate,
    required TimeOfDay selectedTime,
  }) async {
    final reservation = StaffReservation(
      id: 'res-1',
      customerName: 'Mina Park',
      phone: '010-1234-5678',
      partySize: 4,
      reservationStart: DateTime.parse('2026-07-09T18:30:00+09:00'),
      reservationEnd: DateTime.parse('2026-07-09T20:10:00+09:00'),
      seatingPreference: 'room',
      resourceIds: const ['room_1'],
      notes: 'Birthday',
      allergyNotes: null,
      status: 'confirmed',
      source: 'staff_manual',
      version: 2,
      finalBillKrw: null,
      privateRoomMinimumSpendKrw: 200000,
      actualSeatedAt: null,
      completedAt: null,
      warnings: const [],
    );

    return DashboardSnapshot(
      floor: FloorState(
        date: DateTime(2026, 7, 9),
        selectedTime: DateTime.parse('2026-07-09T18:00:00+09:00'),
        resources: [
          FloorResource(
            id: 'table_1',
            label: 'Table 1',
            resourceType: 'table',
            capacity: 3,
            status: 'empty',
            currentReservation: null,
            nextReservation: reservation,
          ),
          FloorResource(
            id: 'room_1',
            label: 'Room 1',
            resourceType: 'room',
            capacity: 6,
            status: 'occupied',
            currentReservation: reservation,
            nextReservation: null,
          ),
        ],
      ),
      reservations: [reservation],
      customers: const [
        CustomerSummary(
          id: 'cust-1',
          name: 'Mina Park',
          phone: '010-1234-5678',
          preferences: 'Window table',
          allergies: null,
          staffNotes: 'Prefers quiet room',
          totalVisits: 5,
          upcomingBookings: 1,
          cancellations: 0,
          noShows: 0,
        ),
      ],
      followups: const [
        ManagerFollowup(
          id: 'follow-1',
          customerName: 'Mina Park',
          phone: '010-1234-5678',
          reason: 'Party over 12',
          partySize: 14,
          reservationStart: null,
          notes: 'Manager should confirm room minimum.',
          status: 'open',
        ),
      ],
      callLogs: const [],
      report: StaffReport(
        range: 'daily',
        startDate: DateTime(2026, 7, 9),
        endDate: DateTime(2026, 7, 9),
        metrics: const {
          'bookings': 7,
          'completed_visits': 3,
          'revenue_krw': 245000,
        },
        charts: const {},
      ),
    );
  }

  @override
  Stream<StaffLiveEvent> liveEvents() => const Stream.empty();
}

void main() {
  testWidgets('shows the staff floor dashboard and main navigation', (
    tester,
  ) async {
    await tester.pumpWidget(
      StaffDashboardApp(
        api: FakeDashboardApi(),
        initialAuthenticated: true,
        connectLiveUpdates: false,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('ABCD Steakhouse'), findsOneWidget);
    expect(find.text('Floor'), findsWidgets);
    expect(find.text('Reservations'), findsWidgets);
    expect(find.text('Customers'), findsWidgets);
    expect(find.text('Follow-ups'), findsWidgets);
    expect(find.text('Reports'), findsWidgets);
    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Upcoming'), findsOneWidget);
    expect(find.text('Seated'), findsOneWidget);
    expect(find.text('Table 1'), findsOneWidget);
    expect(find.text('Room 1'), findsOneWidget);
    expect(find.text('Seat Walk-in'), findsOneWidget);
    expect(find.text('New Reservation'), findsOneWidget);
    expect(find.text('KRW 245,000'), findsOneWidget);

    await tester.tap(find.text('Reservations').first);
    await tester.pumpAndSettle();

    expect(find.text('Reservation Search'), findsOneWidget);
    expect(find.text('Day'), findsOneWidget);
    expect(find.text('Week'), findsOneWidget);
    expect(find.text('Mina Park'), findsWidgets);
  });
}
