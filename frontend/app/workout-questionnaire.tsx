import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

const GOALS = [
  { id: 'build_muscle', label: 'Build Muscle', icon: 'barbell', desc: 'Hypertrophy focused' },
  { id: 'lose_fat', label: 'Lose Fat', icon: 'flame', desc: 'Fat burning workouts' },
  { id: 'general_fitness', label: 'General Fitness', icon: 'fitness', desc: 'Overall health' },
  { id: 'strength', label: 'Build Strength', icon: 'trophy', desc: 'Power & strength' },
];

const FOCUS_AREAS = [
  { id: 'full_body', label: 'Full Body' },
  { id: 'upper_body', label: 'Upper Body' },
  { id: 'lower_body', label: 'Lower Body' },
  { id: 'push', label: 'Push' },
  { id: 'pull', label: 'Pull' },
  { id: 'back', label: 'Back' },
  { id: 'chest', label: 'Chest' },
  { id: 'legs', label: 'Legs' },
  { id: 'glutes', label: 'Glutes' },
  { id: 'arms', label: 'Arms' },
  { id: 'shoulders', label: 'Shoulders' },
  { id: 'core', label: 'Core' },
];

const EQUIPMENT = [
  { id: 'full_gym', label: 'Full Gym' },
  { id: 'barbells', label: 'Barbells' },
  { id: 'dumbbells', label: 'Dumbbells' },
  { id: 'bodyweight', label: 'Body Weight' },
  { id: 'kettlebells', label: 'Kettlebells' },
  { id: 'machines', label: 'Machines' },
  { id: 'cables', label: 'Cables' },
  { id: 'resistance_bands', label: 'Bands' },
];

const DURATIONS = [
  { id: 30, label: '30 min', desc: 'Quick & efficient' },
  { id: 45, label: '45 min', desc: 'Balanced workout' },
  { id: 60, label: '60 min', desc: 'Full session' },
  { id: 90, label: '90 min', desc: 'Extended training' },
];

const DAYS_OPTIONS = [2, 3, 4, 5, 6];

const FITNESS_LEVELS = [
  { id: 'beginner', label: 'Beginner', icon: 'leaf', desc: 'New to fitness or returning after a break' },
  { id: 'intermediate', label: 'Intermediate', icon: 'trending-up', desc: '6+ months consistent training' },
  { id: 'advanced', label: 'Advanced', icon: 'flash', desc: '2+ years serious training' },
];

export default function WorkoutQuestionnaire() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [checkingSubscription, setCheckingSubscription] = useState(false);
  const [formData, setFormData] = useState({
    goal: 'build_muscle',
    focus_areas: ['full_body'] as string[],
    equipment: ['full_gym'] as string[],
    injuries: '',
    days_per_week: 4,
    duration_minutes: 60,
    fitness_level: 'intermediate',
  });

  const toggleSelection = (field: 'focus_areas' | 'equipment', value: string) => {
    const current = formData[field];
    if (current.includes(value)) {
      if (current.length > 1) {
        setFormData({ ...formData, [field]: current.filter((v) => v !== value) });
      }
    } else {
      setFormData({ ...formData, [field]: [...current, value] });
    }
  };

  const handleGenerate = async () => {
    if (!profile?.id) {
      Alert.alert('Error', 'Please complete your profile first');
      return;
    }

    // Check subscription status before generating
    setCheckingSubscription(true);
    try {
      const subResponse = await api.get(`/subscription/check/${profile.id}`);
      if (!subResponse.data.has_access) {
        setCheckingSubscription(false);
        // Redirect to subscription page
        Alert.alert(
          'Subscription Required',
          'Start your free trial to generate personalized AI workouts!',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Start Free Trial', onPress: () => router.push('/subscription') },
          ]
        );
        return;
      }
    } catch (error) {
      console.log('Subscription check error:', error);
      // Allow generation if subscription check fails (failsafe)
    } finally {
      setCheckingSubscription(false);
    }

    setLoading(true);
    try {
      const response = await api.post('/workouts/generate', {
        user_id: profile.id,
        goal: formData.goal,
        focus_areas: formData.focus_areas,
        equipment: formData.equipment,
        injuries: formData.injuries || null,
        days_per_week: formData.days_per_week,
        duration_minutes: formData.duration_minutes,
        fitness_level: formData.fitness_level,
      });

      router.replace(`/workout-detail?id=${response.data.id}`);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate workout. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Choose Training Goal</Text>
      <Text style={styles.stepSubtitle}>What do you want to achieve?</Text>
      
      {GOALS.map((goal) => (
        <TouchableOpacity
          key={goal.id}
          style={[styles.goalCard, formData.goal === goal.id && styles.goalCardActive]}
          onPress={() => setFormData({ ...formData, goal: goal.id })}
        >
          <View style={[styles.goalIcon, formData.goal === goal.id && styles.goalIconActive]}>
            <Ionicons
              name={goal.icon as any}
              size={24}
              color={formData.goal === goal.id ? colors.primary : colors.textSecondary}
            />
          </View>
          <View style={styles.goalContent}>
            <Text style={[styles.goalText, formData.goal === goal.id && styles.goalTextActive]}>
              {goal.label}
            </Text>
            <Text style={styles.goalDesc}>{goal.desc}</Text>
          </View>
          {formData.goal === goal.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Focus Areas</Text>
      <Text style={styles.stepSubtitle}>Select one or more muscle groups</Text>
      
      <View style={styles.chipContainer}>
        {FOCUS_AREAS.map((area) => (
          <TouchableOpacity
            key={area.id}
            style={[styles.chip, formData.focus_areas.includes(area.id) && styles.chipActive]}
            onPress={() => toggleSelection('focus_areas', area.id)}
          >
            <Text style={[styles.chipText, formData.focus_areas.includes(area.id) && styles.chipTextActive]}>
              {area.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Equipment Available</Text>
      <Text style={styles.stepSubtitle}>What equipment do you have access to?</Text>
      
      <View style={styles.chipContainer}>
        {EQUIPMENT.map((eq) => (
          <TouchableOpacity
            key={eq.id}
            style={[styles.chip, formData.equipment.includes(eq.id) && styles.chipActive]}
            onPress={() => toggleSelection('equipment', eq.id)}
          >
            <Text style={[styles.chipText, formData.equipment.includes(eq.id) && styles.chipTextActive]}>
              {eq.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep4 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Workout Duration</Text>
      <Text style={styles.stepSubtitle}>How long do you want each workout to be?</Text>
      
      <View style={styles.durationGrid}>
        {DURATIONS.map((dur) => (
          <TouchableOpacity
            key={dur.id}
            style={[styles.durationCard, formData.duration_minutes === dur.id && styles.durationCardActive]}
            onPress={() => setFormData({ ...formData, duration_minutes: dur.id })}
          >
            <Text style={[styles.durationValue, formData.duration_minutes === dur.id && styles.durationValueActive]}>
              {dur.label}
            </Text>
            <Text style={styles.durationDesc}>{dur.desc}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={[styles.stepTitle, { marginTop: 28 }]}>Days Per Week</Text>
      <Text style={styles.stepSubtitle}>How many days can you train?</Text>
      
      <View style={styles.daysContainer}>
        {DAYS_OPTIONS.map((days) => (
          <TouchableOpacity
            key={days}
            style={[styles.dayBtn, formData.days_per_week === days && styles.dayBtnActive]}
            onPress={() => setFormData({ ...formData, days_per_week: days })}
          >
            <Text style={[styles.dayBtnText, formData.days_per_week === days && styles.dayBtnTextActive]}>
              {days}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={[styles.stepTitle, { marginTop: 28 }]}>Fitness Level</Text>
      <Text style={styles.stepSubtitle}>Choose your current fitness level</Text>
      
      {FITNESS_LEVELS.map((level) => (
        <TouchableOpacity
          key={level.id}
          style={[styles.levelCard, formData.fitness_level === level.id && styles.levelCardActive]}
          onPress={() => setFormData({ ...formData, fitness_level: level.id })}
        >
          <View style={[styles.levelIcon, formData.fitness_level === level.id && styles.levelIconActive]}>
            <Ionicons 
              name={level.icon as any} 
              size={22} 
              color={formData.fitness_level === level.id ? colors.background : colors.primary} 
            />
          </View>
          <View style={styles.levelContent}>
            <Text style={[styles.levelLabel, formData.fitness_level === level.id && styles.levelLabelActive]}>
              {level.label}
            </Text>
            <Text style={styles.levelDesc}>{level.desc}</Text>
          </View>
          {formData.fitness_level === level.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderStep5 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Any Injuries?</Text>
      <Text style={styles.stepSubtitle}>We'll adjust exercises to avoid aggravating injuries</Text>
      
      <TextInput
        style={styles.textInput}
        placeholder="e.g., Lower back pain, knee issues, shoulder injury, or 'None'"
        placeholderTextColor={colors.textMuted}
        value={formData.injuries}
        onChangeText={(text) => setFormData({ ...formData, injuries: text })}
        multiline
      />

      {/* Summary */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Your Workout Program</Text>
        <View style={styles.summaryRow}>
          <Ionicons name="flag" size={18} color={colors.primary} />
          <Text style={styles.summaryText}>
            {GOALS.find(g => g.id === formData.goal)?.label}
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="time" size={18} color={colors.primary} />
          <Text style={styles.summaryText}>
            {formData.duration_minutes} min workouts, {formData.days_per_week}x per week
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="fitness" size={18} color={colors.primary} />
          <Text style={styles.summaryText}>
            {FITNESS_LEVELS.find(l => l.id === formData.fitness_level)?.label || 'Intermediate'} Level
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="body" size={18} color={colors.primary} />
          <Text style={styles.summaryText}>
            {formData.focus_areas.slice(0, 3).join(', ')}
            {formData.focus_areas.length > 3 && ` +${formData.focus_areas.length - 3} more`}
          </Text>
        </View>
      </View>
    </View>
  );

  const totalSteps = 5;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Workout</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        {Array.from({ length: totalSteps }, (_, i) => i + 1).map((s) => (
          <View key={s} style={[styles.progressDot, s <= step && styles.progressDotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
        {step === 5 && renderStep5()}
      </ScrollView>

      {/* Navigation */}
      <View style={styles.navContainer}>
        {step > 1 && (
          <TouchableOpacity style={styles.navBackBtn} onPress={() => setStep(step - 1)}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[styles.navNextBtn, loading && styles.btnDisabled]}
          onPress={step < totalSteps ? () => setStep(step + 1) : handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color={colors.textOnPrimary} />
          ) : (
            <>
              <Text style={styles.navNextText}>
                {step < totalSteps ? 'Continue' : 'Generate Program'}
              </Text>
              <Ionicons name={step < totalSteps ? "arrow-forward" : "sparkles"} size={20} color={colors.textOnPrimary} />
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
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
  progressContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingBottom: 16,
  },
  progressDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceLight,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 20,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  stepSubtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: 24,
  },
  goalCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  goalCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  goalIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surfaceLight,
    justifyContent: 'center',
    alignItems: 'center',
  },
  goalIconActive: {
    backgroundColor: colors.primary + '25',
  },
  goalContent: {
    flex: 1,
    marginLeft: 14,
  },
  goalText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  goalTextActive: {
    color: colors.primary,
  },
  goalDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  chip: {
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 25,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.primary,
  },
  durationGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  durationCard: {
    width: '47%',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
  },
  durationCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  durationValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  durationValueActive: {
    color: colors.primary,
  },
  durationDesc: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  daysContainer: {
    flexDirection: 'row',
    gap: 10,
  },
  dayBtn: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  dayBtnActive: {
    backgroundColor: colors.primary + '20',
    borderColor: colors.primary,
  },
  dayBtnText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  dayBtnTextActive: {
    color: colors.primary,
  },
  textInput: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 100,
    textAlignVertical: 'top',
  },
  summaryCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginTop: 28,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 10,
  },
  summaryText: {
    fontSize: 14,
    color: colors.text,
    flex: 1,
  },
  navContainer: {
    flexDirection: 'row',
    padding: 20,
    gap: 12,
  },
  navBackBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  navNextBtn: {
    flex: 1,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  navNextText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textOnPrimary,
  },
  btnDisabled: {
    opacity: 0.7,
  },
  levelCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 14,
    marginTop: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  levelCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  levelIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  levelIconActive: {
    backgroundColor: colors.primary,
  },
  levelContent: {
    flex: 1,
    marginLeft: 14,
  },
  levelLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  levelLabelActive: {
    color: colors.primary,
  },
  levelDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
