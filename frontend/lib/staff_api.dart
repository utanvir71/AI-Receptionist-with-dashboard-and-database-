import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

abstract class DashboardApi {
  Future<void> login(String password);

  Future<DashboardSnapshot> loadDashboard({
    required DateTime selectedDate,
    required TimeOfDay selectedTime,
  });

  Stream<StaffLiveEvent> liveEvents();
}

class StaffApiException implements Exception {
  StaffApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  bool get isConflict => statusCode == 409;

  @override
  String toString() => message;
}

class StaffApiClient implements DashboardApi {
  StaffApiClient({Uri? baseUri, http.Client? client})
    : baseUri = baseUri ?? defaultStaffApiBaseUri(),
      _client = client ?? http.Client();

  final Uri baseUri;
  final http.Client _client;

  static Uri defaultStaffApiBaseUri() {
    const configured = String.fromEnvironment('API_BASE_URL');
    if (configured.isNotEmpty) {
      return Uri.parse(configured);
    }
    return Uri.base.hasScheme ? Uri.base : Uri.parse('http://localhost:8000');
  }

  @override
  Future<void> login(String password) async {
    await _postJson('/api/staff/auth/login', {'password': password});
  }

  @override
  Future<DashboardSnapshot> loadDashboard({
    required DateTime selectedDate,
    required TimeOfDay selectedTime,
  }) async {
    final date = _dateParam(selectedDate);
    final time = _timeParam(selectedTime);
    final responses = await Future.wait([
      _getJson('/api/staff/floor', query: {'date': date, 'time': time}),
      _getJson('/api/staff/reservations', query: {'date': date}),
      _getJson('/api/staff/customers'),
      _getJson('/api/staff/follow-ups'),
      _getJson('/api/staff/call-logs'),
      _getJson('/api/staff/reports', query: {'range': 'daily', 'date': date}),
    ]);

    return DashboardSnapshot(
      floor: FloorState.fromJson(responses[0]),
      reservations: _items(
        responses[1],
      ).map(StaffReservation.fromJson).toList(),
      customers: _items(responses[2]).map(CustomerSummary.fromJson).toList(),
      followups: _items(responses[3]).map(ManagerFollowup.fromJson).toList(),
      callLogs: _items(responses[4]).map(CallLogEntry.fromJson).toList(),
      report: StaffReport.fromJson(responses[5]),
    );
  }

  Future<StaffReservation> createReservation(ReservationDraft draft) async {
    return StaffReservation.fromJson(
      await _postJson('/api/staff/reservations', draft.toJson()),
    );
  }

  Future<StaffReservation> patchReservation(
    String id,
    Map<String, Object?> payload,
  ) async {
    return StaffReservation.fromJson(
      await _patchJson('/api/staff/reservations/$id', payload),
    );
  }

  Future<StaffReservation> cancelReservation(String id, int expectedVersion) {
    return _versionPost('/api/staff/reservations/$id/cancel', expectedVersion);
  }

  Future<StaffReservation> markArrived(String id, int expectedVersion) {
    return _versionPost('/api/staff/reservations/$id/arrive', expectedVersion);
  }

  Future<StaffReservation> completeReservation(
    String id,
    int expectedVersion,
    int finalBillKrw,
  ) async {
    return StaffReservation.fromJson(
      await _postJson('/api/staff/reservations/$id/complete', {
        'expected_version': expectedVersion,
        'final_bill_krw': finalBillKrw,
      }),
    );
  }

  Future<StaffReservation> markNoShow(String id, int expectedVersion) {
    return _versionPost('/api/staff/reservations/$id/no-show', expectedVersion);
  }

  Future<StaffReservation> createWalkIn(WalkInDraft draft) async {
    return StaffReservation.fromJson(
      await _postJson('/api/staff/walk-ins', draft.toJson()),
    );
  }

  Future<ManagerFollowup> updateFollowup(
    String id, {
    required String status,
    String? notes,
  }) async {
    return ManagerFollowup.fromJson(
      await _patchJson('/api/staff/follow-ups/$id', {
        'status': status,
        'notes': notes,
      }),
    );
  }

  Future<DemoResetResult> resetDemo() async {
    return DemoResetResult.fromJson(
      await _postJson('/api/staff/demo/reset', const {}),
    );
  }

  Future<BackupResult> createBackup() async {
    return BackupResult.fromJson(
      await _postJson('/api/staff/backups', const {}),
    );
  }

  @override
  Stream<StaffLiveEvent> liveEvents() {
    final wsUri = baseUri.replace(
      scheme: baseUri.scheme == 'https' ? 'wss' : 'ws',
      path: '/api/staff/ws',
      query: '',
    );
    final channel = WebSocketChannel.connect(wsUri);
    return channel.stream
        .where((event) => event is String)
        .map(
          (event) => StaffLiveEvent.fromJson(
            jsonDecode(event as String) as Map<String, dynamic>,
          ),
        );
  }

  Future<StaffReservation> _versionPost(
    String path,
    int expectedVersion,
  ) async {
    return StaffReservation.fromJson(
      await _postJson(path, {'expected_version': expectedVersion}),
    );
  }

  Future<Map<String, dynamic>> _getJson(
    String path, {
    Map<String, String?> query = const {},
  }) async {
    final response = await _client.get(_url(path, query: query));
    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, Object?> body,
  ) async {
    final response = await _client.post(
      _url(path),
      headers: const {'content-type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decodeResponse(response);
  }

  Future<Map<String, dynamic>> _patchJson(
    String path,
    Map<String, Object?> body,
  ) async {
    final response = await _client.patch(
      _url(path),
      headers: const {'content-type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decodeResponse(response);
  }

  Uri _url(String path, {Map<String, String?> query = const {}}) {
    return baseUri.replace(
      path: path,
      queryParameters: {
        for (final entry in query.entries)
          if (entry.value != null) entry.key: entry.value,
      },
    );
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) {
        return <String, dynamic>{};
      }
      return jsonDecode(response.body) as Map<String, dynamic>;
    }

    var message = response.body;
    try {
      final parsed = jsonDecode(response.body) as Map<String, dynamic>;
      message = parsed['detail']?.toString() ?? message;
    } on FormatException {
      // Keep the raw response body when the server does not return JSON.
    }
    throw StaffApiException(message, statusCode: response.statusCode);
  }

  static String _dateParam(DateTime date) {
    return '${date.year.toString().padLeft(4, '0')}-'
        '${date.month.toString().padLeft(2, '0')}-'
        '${date.day.toString().padLeft(2, '0')}';
  }

  static String _timeParam(TimeOfDay time) {
    return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
  }
}

class DashboardSnapshot {
  const DashboardSnapshot({
    required this.floor,
    required this.reservations,
    required this.customers,
    required this.followups,
    required this.callLogs,
    required this.report,
  });

  final FloorState floor;
  final List<StaffReservation> reservations;
  final List<CustomerSummary> customers;
  final List<ManagerFollowup> followups;
  final List<CallLogEntry> callLogs;
  final StaffReport report;
}

class StaffReservation {
  const StaffReservation({
    required this.id,
    required this.customerName,
    required this.phone,
    required this.partySize,
    required this.reservationStart,
    required this.reservationEnd,
    required this.seatingPreference,
    required this.resourceIds,
    required this.notes,
    required this.allergyNotes,
    required this.status,
    required this.source,
    required this.version,
    required this.finalBillKrw,
    required this.privateRoomMinimumSpendKrw,
    required this.actualSeatedAt,
    required this.completedAt,
    required this.warnings,
  });

  factory StaffReservation.fromJson(Map<String, dynamic> json) {
    return StaffReservation(
      id: json['id'] as String,
      customerName: json['customer_name'] as String? ?? 'Walk-in',
      phone: json['phone'] as String? ?? '',
      partySize: json['party_size'] as int? ?? 0,
      reservationStart: _dateTime(json['reservation_start']),
      reservationEnd: _dateTime(json['reservation_end']),
      seatingPreference:
          json['seating_preference'] as String? ?? 'no_preference',
      resourceIds: _stringList(json['resource_ids']),
      notes: json['notes'] as String?,
      allergyNotes: json['allergy_notes'] as String?,
      status: json['status'] as String? ?? 'confirmed',
      source: json['source'] as String? ?? 'staff_manual',
      version: json['version'] as int? ?? 1,
      finalBillKrw: json['final_bill_krw'] as int?,
      privateRoomMinimumSpendKrw:
          json['private_room_minimum_spend_krw'] as int?,
      actualSeatedAt: _nullableDateTime(json['actual_seated_at']),
      completedAt: _nullableDateTime(json['completed_at']),
      warnings: _stringList(json['warnings']),
    );
  }

  StaffReservation copyWith({String? status, int? version, int? finalBillKrw}) {
    return StaffReservation(
      id: id,
      customerName: customerName,
      phone: phone,
      partySize: partySize,
      reservationStart: reservationStart,
      reservationEnd: reservationEnd,
      seatingPreference: seatingPreference,
      resourceIds: resourceIds,
      notes: notes,
      allergyNotes: allergyNotes,
      status: status ?? this.status,
      source: source,
      version: version ?? this.version,
      finalBillKrw: finalBillKrw ?? this.finalBillKrw,
      privateRoomMinimumSpendKrw: privateRoomMinimumSpendKrw,
      actualSeatedAt: actualSeatedAt,
      completedAt: completedAt,
      warnings: warnings,
    );
  }

  final String id;
  final String customerName;
  final String phone;
  final int partySize;
  final DateTime reservationStart;
  final DateTime reservationEnd;
  final String seatingPreference;
  final List<String> resourceIds;
  final String? notes;
  final String? allergyNotes;
  final String status;
  final String source;
  final int version;
  final int? finalBillKrw;
  final int? privateRoomMinimumSpendKrw;
  final DateTime? actualSeatedAt;
  final DateTime? completedAt;
  final List<String> warnings;
}

class FloorState {
  const FloorState({
    required this.date,
    required this.selectedTime,
    required this.resources,
  });

  factory FloorState.fromJson(Map<String, dynamic> json) {
    return FloorState(
      date: DateTime.parse(json['date'] as String),
      selectedTime: _dateTime(json['selected_time']),
      resources: _itemsFromList(
        json['resources'],
      ).map(FloorResource.fromJson).toList(),
    );
  }

  final DateTime date;
  final DateTime selectedTime;
  final List<FloorResource> resources;
}

class FloorResource {
  const FloorResource({
    required this.id,
    required this.label,
    required this.resourceType,
    required this.capacity,
    required this.status,
    required this.currentReservation,
    required this.nextReservation,
  });

  factory FloorResource.fromJson(Map<String, dynamic> json) {
    return FloorResource(
      id: json['id'] as String,
      label: json['label'] as String,
      resourceType: json['resource_type'] as String? ?? 'table',
      capacity: json['capacity'] as int? ?? 0,
      status: json['status'] as String? ?? 'empty',
      currentReservation: _reservationOrNull(json['current_reservation']),
      nextReservation: _reservationOrNull(json['next_reservation']),
    );
  }

  final String id;
  final String label;
  final String resourceType;
  final int capacity;
  final String status;
  final StaffReservation? currentReservation;
  final StaffReservation? nextReservation;
}

class CustomerSummary {
  const CustomerSummary({
    required this.id,
    required this.name,
    required this.phone,
    required this.preferences,
    required this.allergies,
    required this.staffNotes,
    required this.totalVisits,
    required this.upcomingBookings,
    required this.cancellations,
    required this.noShows,
  });

  factory CustomerSummary.fromJson(Map<String, dynamic> json) {
    return CustomerSummary(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String,
      preferences: json['preferences'] as String?,
      allergies: json['allergies'] as String?,
      staffNotes: json['staff_notes'] as String?,
      totalVisits: json['total_visits'] as int? ?? 0,
      upcomingBookings: json['upcoming_bookings'] as int? ?? 0,
      cancellations: json['cancellations'] as int? ?? 0,
      noShows: json['no_shows'] as int? ?? 0,
    );
  }

  final String id;
  final String name;
  final String phone;
  final String? preferences;
  final String? allergies;
  final String? staffNotes;
  final int totalVisits;
  final int upcomingBookings;
  final int cancellations;
  final int noShows;
}

class ManagerFollowup {
  const ManagerFollowup({
    required this.id,
    required this.customerName,
    required this.phone,
    required this.reason,
    required this.partySize,
    required this.reservationStart,
    required this.notes,
    required this.status,
  });

  factory ManagerFollowup.fromJson(Map<String, dynamic> json) {
    return ManagerFollowup(
      id: json['id'] as String,
      customerName: json['customer_name'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
      partySize: json['party_size'] as int?,
      reservationStart: _nullableDateTime(json['reservation_start']),
      notes: json['notes'] as String?,
      status: json['status'] as String? ?? 'open',
    );
  }

  final String id;
  final String customerName;
  final String phone;
  final String reason;
  final int? partySize;
  final DateTime? reservationStart;
  final String? notes;
  final String status;
}

class CallLogEntry {
  const CallLogEntry({
    required this.id,
    required this.callTime,
    required this.customerPhone,
    required this.transcript,
    required this.summary,
    required this.actionTaken,
    required this.reservationId,
  });

  factory CallLogEntry.fromJson(Map<String, dynamic> json) {
    return CallLogEntry(
      id: json['id'] as String,
      callTime: _dateTime(json['call_time']),
      customerPhone: json['customer_phone'] as String?,
      transcript: json['transcript'] as String?,
      summary: json['summary'] as String?,
      actionTaken: json['action_taken'] as String?,
      reservationId: json['reservation_id'] as String?,
    );
  }

  final String id;
  final DateTime callTime;
  final String? customerPhone;
  final String? transcript;
  final String? summary;
  final String? actionTaken;
  final String? reservationId;
}

class StaffReport {
  const StaffReport({
    required this.range,
    required this.startDate,
    required this.endDate,
    required this.metrics,
    required this.charts,
  });

  factory StaffReport.fromJson(Map<String, dynamic> json) {
    return StaffReport(
      range: json['range'] as String? ?? 'daily',
      startDate: DateTime.parse(json['start_date'] as String),
      endDate: DateTime.parse(json['end_date'] as String),
      metrics: (json['metrics'] as Map<String, dynamic>? ?? {})
          .cast<String, Object?>(),
      charts: (json['charts'] as Map<String, dynamic>? ?? {})
          .cast<String, Object?>(),
    );
  }

  final String range;
  final DateTime startDate;
  final DateTime endDate;
  final Map<String, Object?> metrics;
  final Map<String, Object?> charts;
}

class StaffLiveEvent {
  const StaffLiveEvent({
    required this.type,
    required this.entity,
    required this.id,
    required this.version,
    required this.occurredAt,
  });

  factory StaffLiveEvent.fromJson(Map<String, dynamic> json) {
    return StaffLiveEvent(
      type: json['type'] as String,
      entity: json['entity'] as String,
      id: json['id'] as String,
      version: json['version'] as int? ?? 1,
      occurredAt: _dateTime(json['occurred_at']),
    );
  }

  final String type;
  final String entity;
  final String id;
  final int version;
  final DateTime occurredAt;
}

class ReservationDraft {
  const ReservationDraft({
    required this.customerName,
    required this.phone,
    required this.partySize,
    required this.reservationStart,
    required this.seatingPreference,
    required this.resourceId,
    required this.notes,
    required this.allergyNotes,
  });

  final String customerName;
  final String phone;
  final int partySize;
  final DateTime reservationStart;
  final String seatingPreference;
  final String? resourceId;
  final String? notes;
  final String? allergyNotes;

  Map<String, Object?> toJson() => {
    'customer_name': customerName,
    'phone': phone,
    'party_size': partySize,
    'reservation_start': reservationStart.toIso8601String(),
    'seating_preference': seatingPreference,
    'resource_id': resourceId,
    'notes': notes,
    'allergy_notes': allergyNotes,
  };
}

class WalkInDraft {
  const WalkInDraft({
    required this.partySize,
    required this.resourceId,
    required this.seatedAt,
    required this.notes,
  });

  final int partySize;
  final String resourceId;
  final DateTime? seatedAt;
  final String? notes;

  Map<String, Object?> toJson() => {
    'party_size': partySize,
    'resource_id': resourceId,
    'seated_at': seatedAt?.toIso8601String(),
    'notes': notes,
  };
}

class DemoResetResult {
  const DemoResetResult({
    required this.reset,
    required this.reservationsCreated,
  });

  factory DemoResetResult.fromJson(Map<String, dynamic> json) {
    return DemoResetResult(
      reset: json['reset'] as bool? ?? false,
      reservationsCreated: json['reservations_created'] as int? ?? 0,
    );
  }

  final bool reset;
  final int reservationsCreated;
}

class BackupResult {
  const BackupResult({
    required this.id,
    required this.filePath,
    required this.status,
    required this.message,
  });

  factory BackupResult.fromJson(Map<String, dynamic> json) {
    return BackupResult(
      id: json['id'] as String? ?? '',
      filePath: json['file_path'] as String? ?? '',
      status: json['status'] as String? ?? '',
      message: json['message'] as String?,
    );
  }

  final String id;
  final String filePath;
  final String status;
  final String? message;
}

List<Map<String, dynamic>> _items(Map<String, dynamic> json) {
  return _itemsFromList(json['items']);
}

List<Map<String, dynamic>> _itemsFromList(Object? value) {
  return (value as List<dynamic>? ?? const [])
      .map((item) => (item as Map<String, dynamic>))
      .toList();
}

StaffReservation? _reservationOrNull(Object? value) {
  if (value == null) {
    return null;
  }
  return StaffReservation.fromJson(value as Map<String, dynamic>);
}

DateTime _dateTime(Object? value) {
  return DateTime.parse(value as String);
}

DateTime? _nullableDateTime(Object? value) {
  if (value == null) {
    return null;
  }
  return DateTime.parse(value as String);
}

List<String> _stringList(Object? value) {
  return (value as List<dynamic>? ?? const [])
      .map((item) => item.toString())
      .toList();
}
