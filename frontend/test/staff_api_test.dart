import 'dart:convert';

import 'package:ai_receptionist_dashboard/staff_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('loads and parses staff dashboard floor state', () async {
    final client = MockClient((request) async {
      if (request.url.path == '/api/staff/floor') {
        expect(request.url.queryParameters['date'], '2026-07-09');
        expect(request.url.queryParameters['time'], '18:00');
        return http.Response(
          jsonEncode({
            'date': '2026-07-09',
            'selected_time': '2026-07-09T18:00:00+09:00',
            'resources': [
              {
                'id': 'table_1',
                'label': 'Table 1',
                'resource_type': 'table',
                'capacity': 3,
                'status': 'empty',
                'current_reservation': null,
                'next_reservation': {
                  'id': 'res-1',
                  'customer_name': 'Mina Park',
                  'phone': '010-1234-5678',
                  'party_size': 4,
                  'reservation_start': '2026-07-09T18:30:00+09:00',
                  'reservation_end': '2026-07-09T20:10:00+09:00',
                  'seating_preference': 'no_preference',
                  'resource_ids': ['table_1'],
                  'notes': 'Window preferred',
                  'allergy_notes': null,
                  'status': 'confirmed',
                  'source': 'staff_manual',
                  'version': 1,
                  'final_bill_krw': null,
                  'private_room_minimum_spend_krw': null,
                  'actual_seated_at': null,
                  'completed_at': null,
                  'warnings': [],
                },
              },
            ],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      if (request.url.path == '/api/staff/reservations') {
        return http.Response(jsonEncode({'items': []}), 200);
      }
      if (request.url.path == '/api/staff/customers') {
        return http.Response(jsonEncode({'items': []}), 200);
      }
      if (request.url.path == '/api/staff/follow-ups') {
        return http.Response(jsonEncode({'items': []}), 200);
      }
      if (request.url.path == '/api/staff/call-logs') {
        return http.Response(jsonEncode({'items': []}), 200);
      }
      if (request.url.path == '/api/staff/reports') {
        return http.Response(
          jsonEncode({
            'range': 'daily',
            'start_date': '2026-07-09',
            'end_date': '2026-07-09',
            'metrics': {'bookings': 0},
            'charts': {},
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });

    final api = StaffApiClient(
      baseUri: Uri.parse('http://localhost'),
      client: client,
    );
    final snapshot = await api.loadDashboard(
      selectedDate: DateTime(2026, 7, 9),
      selectedTime: const TimeOfDay(hour: 18, minute: 0),
    );

    expect(snapshot.floor.resources.single.label, 'Table 1');
    expect(
      snapshot.floor.resources.single.nextReservation?.customerName,
      'Mina Park',
    );
    expect(snapshot.reservations, isEmpty);
    expect(snapshot.report.metrics['bookings'], 0);
  });
}
