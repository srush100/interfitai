import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

const FOOD_PREFERENCES = [
  { id: 'whole_foods', label: 'Whole Foods', desc: 'Natural, unprocessed foods' },
  { id: 'vegan', label: 'Vegan', desc: 'Plant-based only' },
  { id: 'vegetarian', label: 'Vegetarian', desc: 'No meat, fish allowed' },
  { id: 'keto', label: 'Keto', desc: 'Low carb, high fat' },
  { id: 'none', label: 'No Preference', desc: 'Flexible eating' },
];

const SUPPLEMENTS = [
  { id: 'whey_protein', label: 'Whey Protein' },
  { id: 'creatine', label: 'Creatine' },
  { id: 'pre_workout', label: 'Pre-Workout' },
  { id: 'bcaa', label: 'BCAAs' },
  { id: 'multivitamin', label: 'Multivitamin' },
  { id: 'omega3', label: 'Omega-3' },
  { id: 'none', label: 'No Supplements' },
];

const ALLERGIES = [
  { id: 'gluten', label: 'Gluten' },
  { id: 'nuts', label: 'Nuts' },
  { id: 'dairy', label: 'Dairy' },
  { id: 'eggs', label: 'Eggs' },
  { id: 'soy', label: 'Soy' },
  { id: 'shellfish', label: 'Shellfish' },
  { id: 'none', label: 'No Allergies' },
];

export default function MealQuestionnaire() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    food_preferences: 'whole_foods',
    supplements: [] as string[],
    allergies: [] as string[],
  });

  const toggleSelection = (field: 'supplements' | 'allergies', value: string) => {
    const current = formData[field];
    if (value === 'none') {
      setFormData({ ...formData, [field]: ['none'] });
    } else {
      const filtered = current.filter((v) => v !== 'none');
      if (filtered.includes(value)) {
        setFormData({ ...formData, [field]: filtered.filter((v) => v !== value) });
      } else {
        setFormData({ ...formData, [field]: [...filtered, value] });
      }
    }
  };

  const handleGenerate = async () => {
    if (!profile?.id) {
      Alert.alert('Error', 'Please complete your profile first');
      return;
    }

    if (!profile?.calculated_macros) {
      Alert.alert('Error', 'Please set up your profile with body stats to calculate macros');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/mealplans/generate', {
        user_id: profile.id,
        food_preferences: formData.food_preferences,
        supplements: formData.supplements.filter((s) => s !== 'none'),
        allergies: formData.allergies.filter((a) => a !== 'none'),
      });

      router.replace(`/meal-detail?id=${response.data.id}`);
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate meal plan. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const renderStep1 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Food Preferences</Text>
      <Text style={styles.stepSubtitle}>What type of eating style do you prefer?</Text>
      
      {FOOD_PREFERENCES.map((pref) => (
        <TouchableOpacity
          key={pref.id}
          style={[styles.optionCard, formData.food_preferences === pref.id && styles.optionCardActive]}
          onPress={() => setFormData({ ...formData, food_preferences: pref.id })}
        >
          <View style={styles.optionContent}>
            <Text style={[styles.optionTitle, formData.food_preferences === pref.id && styles.optionTitleActive]}>
              {pref.label}
            </Text>
            <Text style={styles.optionDesc}>{pref.desc}</Text>
          </View>
          {formData.food_preferences === pref.id && (
            <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Supplements</Text>
      <Text style={styles.stepSubtitle}>Do you use any supplements?</Text>
      
      <View style={styles.chipContainer}>
        {SUPPLEMENTS.map((supp) => (
          <TouchableOpacity
            key={supp.id}
            style={[
              styles.chip,
              formData.supplements.includes(supp.id) && styles.chipActive,
            ]}
            onPress={() => toggleSelection('supplements', supp.id)}
          >
            <Text style={[styles.chipText, formData.supplements.includes(supp.id) && styles.chipTextActive]}>
              {supp.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Food Allergies</Text>
      <Text style={styles.stepSubtitle}>Do you have any food allergies or sensitivities?</Text>
      
      <View style={styles.chipContainer}>
        {ALLERGIES.map((allergy) => (
          <TouchableOpacity
            key={allergy.id}
            style={[
              styles.chip,
              formData.allergies.includes(allergy.id) && styles.chipActive,
            ]}
            onPress={() => toggleSelection('allergies', allergy.id)}
          >
            <Text style={[styles.chipText, formData.allergies.includes(allergy.id) && styles.chipTextActive]}>
              {allergy.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Summary */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Your Meal Plan Will Include:</Text>
        <View style={styles.summaryRow}>
          <Ionicons name="flame" size={18} color={colors.primary} />
          <Text style={styles.summaryText}>
            {profile?.calculated_macros?.calories || 2000} daily calories
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="barbell" size={18} color="#FF6B6B" />
          <Text style={styles.summaryText}>
            {profile?.calculated_macros?.protein || 150}g protein
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="leaf" size={18} color="#4ECDC4" />
          <Text style={styles.summaryText}>
            {formData.food_preferences.replace(/_/g, ' ')} diet
          </Text>
        </View>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="close" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create Meal Plan</Text>
        <View style={styles.backBtn} />
      </View>

      {/* Progress */}
      <View style={styles.progressContainer}>
        {[1, 2, 3].map((s) => (
          <View key={s} style={[styles.progressDot, s <= step && styles.progressDotActive]} />
        ))}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
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
          onPress={step < 3 ? () => setStep(step + 1) : handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color={colors.background} />
          ) : (
            <>
              <Text style={styles.navNextText}>
                {step < 3 ? 'Continue' : 'Generate Meal Plan'}
              </Text>
              <Ionicons name="arrow-forward" size={20} color={colors.background} />
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
    width: 24,
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
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 18,
    borderRadius: 14,
    marginBottom: 12,
    borderWidth: 2,
    borderColor: colors.border,
  },
  optionCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  optionContent: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  optionTitleActive: {
    color: colors.primary,
  },
  optionDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
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
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: colors.primary,
  },
  summaryCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 14,
    marginTop: 32,
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
    fontSize: 15,
    color: colors.text,
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
    color: colors.background,
  },
  btnDisabled: {
    opacity: 0.7,
  },
});