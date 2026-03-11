import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  Platform,
  ActivityIndicator,
  Modal,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Picker } from '@react-native-picker/picker';
import { colors } from '../src/theme/colors';
import {
  WorkoutReminder,
  loadReminders,
  saveReminders,
  registerForPushNotificationsAsync,
} from '../src/services/notifications';
import {
  isHealthAvailable,
  requestHealthPermissions,
  syncHealthData,
  getHealthConnectionStatus,
  HealthData,
} from '../src/services/health';
import AsyncStorage from '@react-native-async-storage/async-storage';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const DAYS_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

interface ConnectedDevice {
  id: string;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  available: boolean;
}

export default function SettingsScreen() {
  const router = useRouter();
  const [reminders, setReminders] = useState<WorkoutReminder[]>([]);
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingHealth, setSyncingHealth] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [selectedReminderIndex, setSelectedReminderIndex] = useState<number | null>(null);
  const [tempHour, setTempHour] = useState(7);
  const [tempMinute, setTempMinute] = useState(0);
  
  const [connectedDevices, setConnectedDevices] = useState<ConnectedDevice[]>([
    { id: 'apple_health', name: 'Apple Health', icon: 'logo-apple', color: '#FF2D55', connected: false, available: Platform.OS === 'ios' },
    { id: 'google_fit', name: 'Google Fit', icon: 'fitness', color: '#4285F4', connected: false, available: Platform.OS === 'android' },
    { id: 'fitbit', name: 'Fitbit', icon: 'watch', color: '#00B0B9', connected: false, available: true },
    { id: 'garmin', name: 'Garmin', icon: 'navigate', color: '#007CC3', connected: false, available: true },
  ]);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      // Load reminders
      const savedReminders = await loadReminders();
      setReminders(savedReminders);

      // Check health availability
      const healthStatus = await getHealthConnectionStatus();
      
      // Update device connection status
      const storedDevices = await AsyncStorage.getItem('@connected_devices');
      if (storedDevices) {
        const parsed = JSON.parse(storedDevices);
        setConnectedDevices(prev => prev.map(d => ({
          ...d,
          connected: parsed[d.id] || false
        })));
      }

      // Update Apple Health / Google Fit status
      if (healthStatus.connected) {
        setConnectedDevices(prev => prev.map(d => 
          d.id === (Platform.OS === 'ios' ? 'apple_health' : 'google_fit')
            ? { ...d, connected: true }
            : d
        ));
        const data = await syncHealthData();
        setHealthData(data);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleReminder = async (index: number) => {
    const updated = [...reminders];
    updated[index].enabled = !updated[index].enabled;
    setReminders(updated);
    
    if (updated[index].enabled) {
      await registerForPushNotificationsAsync();
    }
    
    await saveReminders(updated);
  };

  const openTimePicker = (index: number) => {
    setSelectedReminderIndex(index);
    setTempHour(reminders[index].hour);
    setTempMinute(reminders[index].minute);
    setShowTimePicker(true);
  };

  const saveTimeSelection = async () => {
    if (selectedReminderIndex === null) return;
    
    const updated = [...reminders];
    updated[selectedReminderIndex].hour = tempHour;
    updated[selectedReminderIndex].minute = tempMinute;
    setReminders(updated);
    await saveReminders(updated);
    setShowTimePicker(false);
    setSelectedReminderIndex(null);
  };

  const connectDevice = async (deviceId: string) => {
    const device = connectedDevices.find(d => d.id === deviceId);
    if (!device) return;

    if (device.connected) {
      // Disconnect
      Alert.alert(
        'Disconnect Device',
        `Are you sure you want to disconnect ${device.name}?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { 
            text: 'Disconnect', 
            style: 'destructive',
            onPress: async () => {
              const updated = connectedDevices.map(d => 
                d.id === deviceId ? { ...d, connected: false } : d
              );
              setConnectedDevices(updated);
              await saveDeviceStatus(updated);
            }
          }
        ]
      );
      return;
    }

    // Connect based on device type
    if (deviceId === 'apple_health' || deviceId === 'google_fit') {
      const available = await isHealthAvailable();
      if (!available) {
        Alert.alert(
          'Not Available',
          `${device.name} is not available on this device.`,
          [{ text: 'OK' }]
        );
        return;
      }

      const granted = await requestHealthPermissions();
      if (granted) {
        const updated = connectedDevices.map(d => 
          d.id === deviceId ? { ...d, connected: true } : d
        );
        setConnectedDevices(updated);
        await saveDeviceStatus(updated);
        
        setSyncingHealth(true);
        const data = await syncHealthData();
        setHealthData(data);
        setSyncingHealth(false);
        
        Alert.alert('Connected', `Successfully connected to ${device.name}!`);
      } else {
        Alert.alert(
          'Permission Denied',
          `Please enable ${device.name} permissions in your device settings.`,
          [{ text: 'OK' }]
        );
      }
    } else if (deviceId === 'fitbit') {
      // Fitbit OAuth flow - would redirect to Fitbit authorization
      Alert.alert(
        'Connect Fitbit',
        'You will be redirected to Fitbit to authorize the connection.',
        [
          { text: 'Cancel', style: 'cancel' },
          { 
            text: 'Continue', 
            onPress: () => {
              // In production, this would open Fitbit OAuth
              // For now, simulate connection
              const updated = connectedDevices.map(d => 
                d.id === deviceId ? { ...d, connected: true } : d
              );
              setConnectedDevices(updated);
              saveDeviceStatus(updated);
              Alert.alert('Connected', 'Fitbit connected successfully!');
            }
          }
        ]
      );
    } else if (deviceId === 'garmin') {
      // Garmin Connect flow
      Alert.alert(
        'Connect Garmin',
        'You will be redirected to Garmin Connect to authorize the connection.',
        [
          { text: 'Cancel', style: 'cancel' },
          { 
            text: 'Continue', 
            onPress: () => {
              // In production, this would open Garmin OAuth
              const updated = connectedDevices.map(d => 
                d.id === deviceId ? { ...d, connected: true } : d
              );
              setConnectedDevices(updated);
              saveDeviceStatus(updated);
              Alert.alert('Connected', 'Garmin connected successfully!');
            }
          }
        ]
      );
    }
  };

  const saveDeviceStatus = async (devices: ConnectedDevice[]) => {
    const status: { [key: string]: boolean } = {};
    devices.forEach(d => { status[d.id] = d.connected; });
    await AsyncStorage.setItem('@connected_devices', JSON.stringify(status));
  };

  const handleSyncHealth = async () => {
    setSyncingHealth(true);
    try {
      const data = await syncHealthData();
      setHealthData(data);
      Alert.alert('Synced', 'Health data updated successfully!');
    } catch (error) {
      Alert.alert('Error', 'Failed to sync health data');
    } finally {
      setSyncingHealth(false);
    }
  };

  const formatTime = (hour: number, minute: number) => {
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 || 12;
    return `${displayHour}:${minute.toString().padStart(2, '0')} ${period}`;
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Connected Devices */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="watch" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>Connected Devices</Text>
          </View>
          
          <View style={styles.card}>
            {connectedDevices.filter(d => d.available).map((device, index) => (
              <TouchableOpacity 
                key={device.id}
                style={[
                  styles.deviceRow,
                  index < connectedDevices.filter(d => d.available).length - 1 && styles.deviceRowBorder
                ]}
                onPress={() => connectDevice(device.id)}
              >
                <View style={styles.deviceInfo}>
                  <View style={[styles.deviceIconContainer, { backgroundColor: device.color + '20' }]}>
                    <Ionicons name={device.icon as any} size={22} color={device.color} />
                  </View>
                  <View>
                    <Text style={styles.deviceName}>{device.name}</Text>
                    <Text style={[
                      styles.deviceStatus,
                      device.connected && styles.deviceStatusConnected
                    ]}>
                      {device.connected ? 'Connected' : 'Tap to connect'}
                    </Text>
                  </View>
                </View>
                
                {device.connected ? (
                  <Ionicons name="checkmark-circle" size={24} color={colors.success} />
                ) : (
                  <Ionicons name="add-circle-outline" size={24} color={colors.textMuted} />
                )}
              </TouchableOpacity>
            ))}

            {/* Sync Button */}
            {connectedDevices.some(d => d.connected) && (
              <TouchableOpacity 
                style={styles.syncButton}
                onPress={handleSyncHealth}
                disabled={syncingHealth}
              >
                {syncingHealth ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <>
                    <Ionicons name="sync" size={18} color={colors.primary} />
                    <Text style={styles.syncButtonText}>Sync All Devices</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
          </View>

          {/* Health Stats */}
          {healthData && connectedDevices.some(d => d.connected) && (
            <View style={[styles.card, { marginTop: 12 }]}>
              <Text style={styles.statsTitle}>Today's Activity</Text>
              <View style={styles.healthStats}>
                <View style={styles.healthStat}>
                  <Ionicons name="footsteps" size={24} color={colors.primary} />
                  <Text style={styles.healthStatValue}>{healthData.steps.toLocaleString()}</Text>
                  <Text style={styles.healthStatLabel}>Steps</Text>
                </View>
                <View style={styles.healthStat}>
                  <Ionicons name="flame" size={24} color="#FF6B6B" />
                  <Text style={styles.healthStatValue}>{healthData.calories}</Text>
                  <Text style={styles.healthStatLabel}>Calories</Text>
                </View>
                <View style={styles.healthStat}>
                  <Ionicons name="walk" size={24} color="#45B7D1" />
                  <Text style={styles.healthStatValue}>{healthData.distance} km</Text>
                  <Text style={styles.healthStatLabel}>Distance</Text>
                </View>
              </View>
            </View>
          )}
        </View>

        {/* Workout Reminders */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="notifications" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>Workout Reminders</Text>
          </View>
          
          <View style={styles.card}>
            <Text style={styles.reminderDesc}>
              Set your preferred workout times for each day
            </Text>
            
            {reminders.map((reminder, index) => (
              <View key={reminder.id} style={styles.reminderItem}>
                <View style={styles.reminderLeft}>
                  <Text style={[
                    styles.reminderDay,
                    reminder.enabled && styles.reminderDayActive
                  ]}>
                    {DAYS[reminder.dayOfWeek]}
                  </Text>
                </View>
                
                <TouchableOpacity 
                  style={styles.timeButton}
                  onPress={() => openTimePicker(index)}
                >
                  <Ionicons name="time-outline" size={16} color={colors.primary} />
                  <Text style={styles.timeButtonText}>
                    {formatTime(reminder.hour, reminder.minute)}
                  </Text>
                </TouchableOpacity>
                
                <Switch
                  value={reminder.enabled}
                  onValueChange={() => toggleReminder(index)}
                  trackColor={{ false: colors.border, true: colors.primary + '60' }}
                  thumbColor={reminder.enabled ? colors.primary : colors.textMuted}
                  ios_backgroundColor={colors.border}
                />
              </View>
            ))}
          </View>
        </View>

        {/* App Info */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="information-circle" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>About</Text>
          </View>
          
          <View style={styles.card}>
            <View style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Version</Text>
              <Text style={styles.aboutValue}>1.0.0</Text>
            </View>
            <View style={[styles.aboutRow, { borderBottomWidth: 0 }]}>
              <Text style={styles.aboutLabel}>Build</Text>
              <Text style={styles.aboutValue}>2025.03</Text>
            </View>
          </View>
        </View>
      </ScrollView>

      {/* Time Picker Modal */}
      <Modal
        visible={showTimePicker}
        transparent
        animationType="slide"
        onRequestClose={() => setShowTimePicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.timePickerModal}>
            <View style={styles.timePickerHeader}>
              <Text style={styles.timePickerTitle}>
                Set Reminder Time
              </Text>
              <Text style={styles.timePickerSubtitle}>
                {selectedReminderIndex !== null ? DAYS[reminders[selectedReminderIndex].dayOfWeek] : ''}
              </Text>
            </View>
            
            <View style={styles.pickerContainer}>
              <Picker
                selectedValue={tempHour}
                onValueChange={setTempHour}
                style={styles.picker}
                itemStyle={styles.pickerItem}
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <Picker.Item 
                    key={i} 
                    label={`${i % 12 || 12} ${i < 12 ? 'AM' : 'PM'}`} 
                    value={i} 
                  />
                ))}
              </Picker>
              
              <Text style={styles.pickerSeparator}>:</Text>
              
              <Picker
                selectedValue={tempMinute}
                onValueChange={setTempMinute}
                style={styles.picker}
                itemStyle={styles.pickerItem}
              >
                {[0, 15, 30, 45].map(min => (
                  <Picker.Item 
                    key={min} 
                    label={min.toString().padStart(2, '0')} 
                    value={min} 
                  />
                ))}
              </Picker>
            </View>
            
            <View style={styles.timePickerActions}>
              <TouchableOpacity 
                style={styles.cancelBtn}
                onPress={() => setShowTimePicker(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={styles.saveBtn}
                onPress={saveTimeSelection}
              >
                <Text style={styles.saveBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loader: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
  },
  // Device styles
  deviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
  },
  deviceRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  deviceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  deviceIconContainer: {
    width: 44,
    height: 44,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  deviceName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  deviceStatus: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 2,
  },
  deviceStatusConnected: {
    color: colors.success,
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary + '15',
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 12,
  },
  syncButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
  },
  statsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: 12,
    textAlign: 'center',
  },
  healthStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  healthStat: {
    alignItems: 'center',
    gap: 6,
  },
  healthStatValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  healthStatLabel: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  // Reminder styles
  reminderDesc: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  reminderItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  reminderLeft: {
    flex: 1,
  },
  reminderDay: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  reminderDayActive: {
    color: colors.text,
    fontWeight: '600',
  },
  timeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primary + '15',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 20,
    marginRight: 16,
  },
  timeButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.primary,
  },
  // About styles
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  aboutLabel: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  aboutValue: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
  },
  // Time Picker Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  timePickerModal: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    paddingBottom: Platform.OS === 'ios' ? 40 : 20,
  },
  timePickerHeader: {
    alignItems: 'center',
    marginBottom: 20,
  },
  timePickerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  timePickerSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  pickerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  picker: {
    width: 120,
    height: 180,
  },
  pickerItem: {
    fontSize: 20,
    color: colors.text,
  },
  pickerSeparator: {
    fontSize: 24,
    fontWeight: '600',
    color: colors.text,
    marginHorizontal: 10,
  },
  timePickerActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 12,
    backgroundColor: colors.border,
    alignItems: 'center',
  },
  cancelBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  saveBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
});
