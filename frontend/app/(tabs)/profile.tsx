import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  TextInput,
  ActivityIndicator,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pedometer } from 'expo-sensors';
import * as ImagePicker from 'expo-image-picker';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

const DEVICES = [
  { id: 'apple_health', name: 'Apple Health', icon: 'fitness' },
  { id: 'google_fit', name: 'Google Fit', icon: 'logo-google' },
  { id: 'fitbit', name: 'Fitbit', icon: 'watch' },
  { id: 'garmin', name: 'Garmin', icon: 'navigate' },
];

const GOALS = [
  { id: 'weight_loss', label: 'Lose Weight' },
  { id: 'maintenance', label: 'Maintain' },
  { id: 'muscle_building', label: 'Build Muscle' },
];

const ACTIVITY_LEVELS = [
  { id: 'sedentary', label: 'Sedentary' },
  { id: 'light', label: 'Light' },
  { id: 'moderate', label: 'Moderate' },
  { id: 'active', label: 'Active' },
  { id: 'very_active', label: 'Very Active' },
];

export default function ProfileScreen() {
  const router = useRouter();
  const { profile, updateProfile, setOnboarded } = useUserStore();
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({
    weight: profile?.weight?.toString() || '',
    height: profile?.height?.toString() || '',
    age: profile?.age?.toString() || '',
    goal: profile?.goal || 'muscle_building',
    activity_level: profile?.activity_level || 'moderate',
  });
  const [saving, setSaving] = useState(false);
  const [isPedometerAvailable, setIsPedometerAvailable] = useState(false);
  const [stepCount, setStepCount] = useState(0);
  const [connectedDevices, setConnectedDevices] = useState<string[]>([]);
  const [stepGoal, setStepGoal] = useState(10000);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [calorieAdjustment, setCalorieAdjustment] = useState(0);
  const [showAdjustmentGuide, setShowAdjustmentGuide] = useState(false);

  useEffect(() => {
    checkPedometer();
    loadDevices();
    loadStepGoal();
  }, []);

  const pickProfileImage = async () => {
    try {
      const permissionResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
      
      if (permissionResult.granted === false) {
        Alert.alert('Permission Required', 'Please allow access to your photo library.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.5,
        base64: true,
      });

      if (!result.canceled && result.assets[0].base64) {
        setUploadingPhoto(true);
        try {
          await updateProfile({
            profile_image: result.assets[0].base64,
          });
          Alert.alert('Success', 'Profile picture updated!');
        } catch (error) {
          Alert.alert('Error', 'Failed to update profile picture');
        } finally {
          setUploadingPhoto(false);
        }
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to pick image');
    }
  };

  const checkPedometer = async () => {
    const available = await Pedometer.isAvailableAsync();
    setIsPedometerAvailable(available);

    if (available) {
      const end = new Date();
      const start = new Date();
      start.setHours(0, 0, 0, 0);

      const result = await Pedometer.getStepCountAsync(start, end);
      if (result) {
        setStepCount(result.steps);
        // Log steps to backend
        if (profile?.id) {
          try {
            await api.post(`/steps/log?user_id=${profile.id}&steps=${result.steps}&source=device`);
          } catch (error) {
            console.log('Error logging steps:', error);
          }
        }
      }
    }
  };

  const loadDevices = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/devices/${profile.id}`);
      setConnectedDevices(response.data.filter((d: any) => d.connected).map((d: any) => d.device_type));
    } catch (error) {
      console.log('Error loading devices:', error);
    }
  };

  const loadStepGoal = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/steps/goal/${profile.id}`);
      setStepGoal(response.data.daily_steps_goal);
    } catch (error) {
      console.log('Error loading step goal:', error);
    }
  };

  const handleSaveProfile = async () => {
    if (!editData.weight || !editData.height || !editData.age) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setSaving(true);
    try {
      await updateProfile({
        weight: parseFloat(editData.weight),
        height: parseFloat(editData.height),
        age: parseInt(editData.age),
        goal: editData.goal,
        activity_level: editData.activity_level,
      });
      setEditing(false);
      Alert.alert('Success', 'Profile and goals updated!');
    } catch (error) {
      Alert.alert('Error', 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const toggleReminders = async (value: boolean) => {
    try {
      await updateProfile({ reminders_enabled: value });
    } catch (error) {
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const toggleMotivation = async (value: boolean) => {
    try {
      await updateProfile({ motivation_enabled: value });
    } catch (error) {
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const connectDevice = async (deviceId: string) => {
    if (!profile?.id) return;
    try {
      await api.post(`/devices/connect?user_id=${profile.id}&device_type=${deviceId}`);
      setConnectedDevices([...connectedDevices, deviceId]);
      Alert.alert('Success', `${deviceId.replace('_', ' ')} connected! (Demo mode)`);
    } catch (error) {
      Alert.alert('Error', 'Failed to connect device');
    }
  };

  const disconnectDevice = async (deviceId: string) => {
    if (!profile?.id) return;
    try {
      await api.delete(`/devices/disconnect?user_id=${profile.id}&device_type=${deviceId}`);
      setConnectedDevices(connectedDevices.filter((d) => d !== deviceId));
    } catch (error) {
      Alert.alert('Error', 'Failed to disconnect device');
    }
  };

  const updateStepGoal = async (newGoal: number) => {
    if (!profile?.id) return;
    try {
      await api.post('/steps/goal', {
        user_id: profile.id,
        daily_steps_goal: newGoal,
      });
      setStepGoal(newGoal);
    } catch (error) {
      Alert.alert('Error', 'Failed to update step goal');
    }
  };

  const handleLogout = () => {
    Alert.alert(
      'Reset Profile',
      'This will reset your profile. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await setOnboarded(false);
            router.replace('/onboarding');
          },
        },
      ]
    );
  };

  const macros = profile?.calculated_macros;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>Profile</Text>

        {/* User Info Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <TouchableOpacity onPress={pickProfileImage} style={styles.avatarContainer}>
              {uploadingPhoto ? (
                <View style={styles.avatar}>
                  <ActivityIndicator size="small" color={colors.primary} />
                </View>
              ) : profile?.profile_image ? (
                <Image
                  source={{ uri: `data:image/jpeg;base64,${profile.profile_image}` }}
                  style={styles.avatarImage}
                />
              ) : (
                <View style={styles.avatar}>
                  <Ionicons name="person" size={32} color={colors.primary} />
                </View>
              )}
              <View style={styles.avatarEditBadge}>
                <Ionicons name="camera" size={12} color={colors.background} />
              </View>
            </TouchableOpacity>
            <View style={styles.userInfo}>
              <Text style={styles.userName}>{profile?.name || 'User'}</Text>
              <Text style={styles.userGoal}>
                Goal: {profile?.goal?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.editBtn}
              onPress={() => setEditing(!editing)}
            >
              <Ionicons name={editing ? 'close' : 'pencil'} size={20} color={colors.primary} />
            </TouchableOpacity>
          </View>

          {editing ? (
            <View style={styles.editForm}>
              <View style={styles.editRow}>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Weight (kg)</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.weight}
                    onChangeText={(text) => setEditData({ ...editData, weight: text })}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Height (cm)</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.height}
                    onChangeText={(text) => setEditData({ ...editData, height: text })}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Age</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.age}
                    onChangeText={(text) => setEditData({ ...editData, age: text })}
                    keyboardType="number-pad"
                  />
                </View>
              </View>

              {/* Goal Selector */}
              <Text style={styles.editLabel}>Fitness Goal</Text>
              <View style={styles.goalSelector}>
                {GOALS.map((goal) => (
                  <TouchableOpacity
                    key={goal.id}
                    style={[styles.goalBtn, editData.goal === goal.id && styles.goalBtnActive]}
                    onPress={() => setEditData({ ...editData, goal: goal.id })}
                  >
                    <Text style={[styles.goalBtnText, editData.goal === goal.id && styles.goalBtnTextActive]}>
                      {goal.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Activity Level Selector */}
              <Text style={styles.editLabel}>Activity Level</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.activityScroll}>
                {ACTIVITY_LEVELS.map((level) => (
                  <TouchableOpacity
                    key={level.id}
                    style={[styles.activityBtn, editData.activity_level === level.id && styles.activityBtnActive]}
                    onPress={() => setEditData({ ...editData, activity_level: level.id })}
                  >
                    <Text style={[styles.activityBtnText, editData.activity_level === level.id && styles.activityBtnTextActive]}>
                      {level.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>

              <TouchableOpacity
                style={styles.saveBtn}
                onPress={handleSaveProfile}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color={colors.background} />
                ) : (
                  <Text style={styles.saveBtnText}>Save Changes</Text>
                )}
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.statsRow}>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.weight}kg</Text>
                <Text style={styles.statLabel}>Weight</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.height}cm</Text>
                <Text style={styles.statLabel}>Height</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.age}</Text>
                <Text style={styles.statLabel}>Age</Text>
              </View>
            </View>
          )}
        </View>

        {/* Macros Card with Calorie Adjustment */}
        {macros && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Your Daily Targets</Text>
            
            {/* Calorie Adjuster */}
            <View style={styles.calorieAdjuster}>
              <TouchableOpacity 
                style={styles.adjustBtn}
                onPress={() => setCalorieAdjustment(prev => prev - 50)}
              >
                <Ionicons name="remove" size={24} color={colors.text} />
              </TouchableOpacity>
              
              <View style={styles.calorieDisplay}>
                <Text style={styles.calorieValue}>
                  {macros.calories + calorieAdjustment}
                </Text>
                <Text style={styles.calorieUnit}>calories</Text>
                {calorieAdjustment !== 0 && (
                  <Text style={styles.adjustmentLabel}>
                    {calorieAdjustment > 0 ? '+' : ''}{calorieAdjustment} from calculated
                  </Text>
                )}
              </View>
              
              <TouchableOpacity 
                style={styles.adjustBtn}
                onPress={() => setCalorieAdjustment(prev => prev + 50)}
              >
                <Ionicons name="add" size={24} color={colors.text} />
              </TouchableOpacity>
            </View>

            {/* Quick Adjustment Buttons */}
            <View style={styles.quickAdjustRow}>
              {[-200, -100, 0, 100, 200].map((adj) => (
                <TouchableOpacity
                  key={adj}
                  style={[
                    styles.quickAdjustBtn,
                    calorieAdjustment === adj && styles.quickAdjustBtnActive
                  ]}
                  onPress={() => setCalorieAdjustment(adj)}
                >
                  <Text style={[
                    styles.quickAdjustText,
                    calorieAdjustment === adj && styles.quickAdjustTextActive
                  ]}>
                    {adj === 0 ? 'Base' : adj > 0 ? `+${adj}` : adj}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Help Toggle */}
            <TouchableOpacity 
              style={styles.helpToggle}
              onPress={() => setShowAdjustmentGuide(!showAdjustmentGuide)}
            >
              <Ionicons 
                name={showAdjustmentGuide ? "chevron-up" : "help-circle-outline"} 
                size={18} 
                color={colors.textSecondary} 
              />
              <Text style={styles.helpToggleText}>
                {showAdjustmentGuide ? 'Hide guide' : 'Not seeing results?'}
              </Text>
            </TouchableOpacity>

            {/* Adjustment Guide */}
            {showAdjustmentGuide && (
              <View style={styles.adjustmentGuide}>
                <TouchableOpacity 
                  style={styles.guideOption}
                  onPress={() => setCalorieAdjustment(-200)}
                >
                  <View style={styles.guideIconWrap}>
                    <Ionicons name="trending-down" size={18} color="#FF6B6B" />
                  </View>
                  <View style={styles.guideContent}>
                    <Text style={styles.guideTitle}>Weight not moving?</Text>
                    <Text style={styles.guideDesc}>Try reducing by 100-200 cal</Text>
                  </View>
                </TouchableOpacity>
                
                <TouchableOpacity 
                  style={styles.guideOption}
                  onPress={() => setCalorieAdjustment(0)}
                >
                  <View style={styles.guideIconWrap}>
                    <Ionicons name="checkmark-circle" size={18} color="#4ECDC4" />
                  </View>
                  <View style={styles.guideContent}>
                    <Text style={styles.guideTitle}>Progress is steady?</Text>
                    <Text style={styles.guideDesc}>Keep your current target</Text>
                  </View>
                </TouchableOpacity>
                
                <TouchableOpacity 
                  style={styles.guideOption}
                  onPress={() => setCalorieAdjustment(200)}
                >
                  <View style={styles.guideIconWrap}>
                    <Ionicons name="trending-up" size={18} color={colors.primary} />
                  </View>
                  <View style={styles.guideContent}>
                    <Text style={styles.guideTitle}>Losing too fast / low energy?</Text>
                    <Text style={styles.guideDesc}>Try adding 100-200 cal</Text>
                  </View>
                </TouchableOpacity>
              </View>
            )}

            {/* Macros Grid */}
            <View style={styles.macrosDivider} />
            <View style={styles.macrosGrid}>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#FF6B6B' }]}>
                  {macros.protein}g
                </Text>
                <Text style={styles.macroLabel}>Protein</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#4ECDC4' }]}>
                  {Math.round(macros.carbs + (calorieAdjustment / 4))}g
                </Text>
                <Text style={styles.macroLabel}>Carbs</Text>
                {calorieAdjustment !== 0 && (
                  <Text style={styles.macroAdjustment}>
                    {calorieAdjustment > 0 ? '+' : ''}{Math.round(calorieAdjustment / 4)}g
                  </Text>
                )}
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#FFD93D' }]}>
                  {macros.fats}g
                </Text>
                <Text style={styles.macroLabel}>Fats</Text>
              </View>
            </View>
            
            <View style={styles.tdeeRow}>
              <Text style={styles.tdeeLabel}>TDEE: {macros.tdee} cal</Text>
              <Text style={styles.tdeeLabel}>BMR: {macros.bmr} cal</Text>
            </View>
          </View>
        )}

        {/* Step Tracking */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Step Tracking</Text>
          <View style={styles.stepsDisplay}>
            <Ionicons name="footsteps" size={32} color={colors.primary} />
            <View style={styles.stepsInfo}>
              <Text style={styles.stepsValue}>{stepCount.toLocaleString()}</Text>
              <Text style={styles.stepsGoal}>/ {stepGoal.toLocaleString()} steps</Text>
            </View>
          </View>
          <View style={styles.stepGoalBtns}>
            {[5000, 10000, 15000].map((goal) => (
              <TouchableOpacity
                key={goal}
                style={[styles.stepGoalBtn, stepGoal === goal && styles.stepGoalBtnActive]}
                onPress={() => updateStepGoal(goal)}
              >
                <Text style={[styles.stepGoalBtnText, stepGoal === goal && styles.stepGoalBtnTextActive]}>
                  {(goal / 1000)}K
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {!isPedometerAvailable && (
            <Text style={styles.pedometerWarning}>
              Step counting not available on this device
            </Text>
          )}
        </View>

        {/* Connected Devices */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Connected Devices</Text>
          {DEVICES.map((device) => (
            <View key={device.id} style={styles.deviceRow}>
              <View style={styles.deviceInfo}>
                <Ionicons name={device.icon as any} size={24} color={colors.textSecondary} />
                <Text style={styles.deviceName}>{device.name}</Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.connectBtn,
                  connectedDevices.includes(device.id) && styles.disconnectBtn,
                ]}
                onPress={() =>
                  connectedDevices.includes(device.id)
                    ? disconnectDevice(device.id)
                    : connectDevice(device.id)
                }
              >
                <Text
                  style={[
                    styles.connectBtnText,
                    connectedDevices.includes(device.id) && styles.disconnectBtnText,
                  ]}
                >
                  {connectedDevices.includes(device.id) ? 'Disconnect' : 'Connect'}
                </Text>
              </TouchableOpacity>
            </View>
          ))}
        </View>

        {/* Settings */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Notifications</Text>
          
          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Ionicons name="notifications" size={22} color={colors.textSecondary} />
              <Text style={styles.settingLabel}>Workout Reminders</Text>
            </View>
            <Switch
              value={profile?.reminders_enabled ?? true}
              onValueChange={toggleReminders}
              trackColor={{ false: colors.surfaceLight, true: colors.primary + '50' }}
              thumbColor={profile?.reminders_enabled ? colors.primary : colors.textMuted}
            />
          </View>

          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Ionicons name="flash" size={22} color={colors.textSecondary} />
              <Text style={styles.settingLabel}>Daily Motivation</Text>
            </View>
            <Switch
              value={profile?.motivation_enabled ?? true}
              onValueChange={toggleMotivation}
              trackColor={{ false: colors.surfaceLight, true: colors.primary + '50' }}
              thumbColor={profile?.motivation_enabled ? colors.primary : colors.textMuted}
            />
          </View>
        </View>

        {/* Subscription */}
        <TouchableOpacity
          style={styles.subscriptionCard}
          onPress={() => router.push('/subscription')}
        >
          <View style={styles.subscriptionInfo}>
            <Ionicons name="diamond" size={24} color={colors.primary} />
            <View style={styles.subscriptionText}>
              <Text style={styles.subscriptionTitle}>Premium Membership</Text>
              <Text style={styles.subscriptionStatus}>
                {profile?.subscription_status === 'free'
                  ? 'Upgrade for full access'
                  : `${profile?.subscription_status} plan active`}
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
        </TouchableOpacity>

        {/* Reset */}
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out" size={20} color={colors.error} />
          <Text style={styles.logoutText}>Reset Profile</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 100,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 20,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  userInfo: {
    flex: 1,
    marginLeft: 16,
  },
  userName: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
  },
  userGoal: {
    fontSize: 14,
    color: colors.primary,
    marginTop: 2,
  },
  editBtn: {
    padding: 8,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  editForm: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  editRow: {
    flexDirection: 'row',
    gap: 12,
  },
  editField: {
    flex: 1,
  },
  editLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 6,
  },
  editInput: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.text,
    textAlign: 'center',
  },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 16,
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  macrosGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  macroItem: {
    alignItems: 'center',
  },
  macroValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  macroLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  macroAdjustment: {
    fontSize: 11,
    color: '#4ECDC4',
    marginTop: 2,
  },
  tdeeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tdeeLabel: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  stepsDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginBottom: 16,
  },
  stepsInfo: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  stepsValue: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.primary,
  },
  stepsGoal: {
    fontSize: 16,
    color: colors.textSecondary,
    marginLeft: 4,
  },
  stepGoalBtns: {
    flexDirection: 'row',
    gap: 12,
  },
  stepGoalBtn: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.surfaceLight,
    alignItems: 'center',
  },
  stepGoalBtnActive: {
    backgroundColor: colors.primary + '20',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  stepGoalBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  stepGoalBtnTextActive: {
    color: colors.primary,
  },
  pedometerWarning: {
    fontSize: 12,
    color: colors.warning,
    marginTop: 12,
    textAlign: 'center',
  },
  deviceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  deviceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  deviceName: {
    fontSize: 15,
    color: colors.text,
  },
  connectBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.primary,
  },
  disconnectBtn: {
    backgroundColor: colors.surfaceLight,
  },
  connectBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.background,
  },
  disconnectBtnText: {
    color: colors.textSecondary,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingLabel: {
    fontSize: 15,
    color: colors.text,
  },
  subscriptionCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.primary + '50',
  },
  subscriptionInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  subscriptionText: {
    gap: 4,
  },
  subscriptionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  subscriptionStatus: {
    fontSize: 13,
    color: colors.primary,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    marginTop: 8,
  },
  logoutText: {
    fontSize: 16,
    color: colors.error,
  },
  goalSelector: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  goalBtn: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.surfaceLight,
    alignItems: 'center',
  },
  goalBtnActive: {
    backgroundColor: colors.primary,
  },
  goalBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  goalBtnTextActive: {
    color: colors.background,
  },
  activityScroll: {
    marginBottom: 16,
  },
  activityBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.surfaceLight,
    marginRight: 8,
  },
  activityBtnActive: {
    backgroundColor: colors.primary,
  },
  activityBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  activityBtnTextActive: {
    color: colors.background,
  },
  avatarContainer: {
    position: 'relative',
  },
  avatarImage: {
    width: 64,
    height: 64,
    borderRadius: 32,
  },
  avatarEditBadge: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.surface,
  },
  // Calorie Adjustment Styles
  calorieAdjuster: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 20,
    marginBottom: 16,
  },
  adjustBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calorieDisplay: {
    alignItems: 'center',
    minWidth: 140,
  },
  calorieValue: {
    fontSize: 36,
    fontWeight: '700',
    color: colors.primary,
  },
  calorieUnit: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  adjustmentLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 4,
  },
  quickAdjustRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 16,
  },
  quickAdjustBtn: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    backgroundColor: colors.surfaceLight,
  },
  quickAdjustBtnActive: {
    backgroundColor: colors.primary,
  },
  quickAdjustText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  quickAdjustTextActive: {
    color: colors.background,
  },
  helpToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
  },
  helpToggleText: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  adjustmentGuide: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    gap: 8,
  },
  guideOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 10,
    backgroundColor: colors.surface,
    borderRadius: 10,
  },
  guideIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  guideContent: {
    flex: 1,
  },
  guideTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
  guideDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  macrosDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 16,
  },
});