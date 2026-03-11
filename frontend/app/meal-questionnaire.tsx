import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

const EATING_STYLES = [
  { id: 'none', label: 'No Preference', desc: 'Flexible eating' },
  { id: 'balanced', label: 'Balanced', desc: 'Well-rounded nutrition' },
  { id: 'whole_foods', label: 'Whole Foods', desc: 'Natural, unprocessed' },
  { id: 'keto', label: 'Keto', desc: 'Low carb, high fat' },
  { id: 'paleo', label: 'Paleo', desc: 'Ancestral eating' },
  { id: 'carnivore', label: 'Carnivore', desc: 'Meat-based diet' },
  { id: 'vegetarian', label: 'Vegetarian', desc: 'No meat or fish' },
  { id: 'vegan', label: 'Vegan', desc: 'Plant-based only' },
];

const ALLERGIES = [
  { id: 'gluten', label: 'Gluten' },
  { id: 'nuts', label: 'Nuts' },
  { id: 'dairy', label: 'Dairy' },
  { id: 'eggs', label: 'Eggs' },
  { id: 'soy', label: 'Soy' },
  { id: 'shellfish', label: 'Shellfish' },
  { id: 'lactose', label: 'Lactose' },
  { id: 'none', label: 'No Allergies' },
];

export default function MealQuestionnaire() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [checkingSubscription, setCheckingSubscription] = useState(false);
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const [formData, setFormData] = useState({
    eating_style: 'none',
    preferred_foods: '',
    foods_to_avoid: '',
    allergies: [] as string[],
  });

  // Track keyboard visibility
  useEffect(() => {
    const keyboardWillShow = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      () => {
        setKeyboardVisible(true);
        // Scroll down a bit when keyboard opens to show the text input
        setTimeout(() => {
          scrollViewRef.current?.scrollToEnd({ animated: true });
        }, 100);
      }
    );
    const keyboardWillHide = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      () => setKeyboardVisible(false)
    );

    return () => {
      keyboardWillShow.remove();
      keyboardWillHide.remove();
    };
  }, []);

  const toggleAllergy = (value: string) => {
    const current = formData.allergies;
    if (value === 'none') {
      setFormData({ ...formData, allergies: ['none'] });
    } else {
      const filtered = current.filter((v) => v !== 'none');
      if (filtered.includes(value)) {
        setFormData({ ...formData, allergies: filtered.filter((v) => v !== value) });
      } else {
        setFormData({ ...formData, allergies: [...filtered, value] });
      }
    }
  };

  const handleGenerate = async () => {
    console.log('Generate button pressed');
    console.log('Profile:', profile);
    console.log('Profile ID:', profile?.id);
    console.log('Calculated Macros:', profile?.calculated_macros);
    
    if (!profile?.id) {
      Alert.alert('Profile Required', 'Please complete the onboarding to set up your profile first.', [
        { text: 'OK', onPress: () => router.push('/onboarding') }
      ]);
      return;
    }

    if (!profile?.calculated_macros) {
      Alert.alert('Profile Incomplete', 'Please complete your profile with body stats to calculate your macros.', [
        { text: 'OK', onPress: () => router.push('/onboarding') }
      ]);
      return;
    }

    // Check subscription status before generating
    setCheckingSubscription(true);
    try {
      console.log('Checking subscription for:', profile.id);
      const subResponse = await api.get(`/subscription/check/${profile.id}`);
      console.log('Subscription response:', subResponse.data);
      if (!subResponse.data.has_access) {
        setCheckingSubscription(false);
        Alert.alert(
          'Subscription Required',
          'Start your free trial to generate personalized AI meal plans!',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Start Free Trial', onPress: () => router.push('/subscription') },
          ]
        );
        return;
      }
    } catch (error) {
      console.log('Subscription check error:', error);
    } finally {
      setCheckingSubscription(false);
    }

    console.log('Starting meal plan generation...');
    setLoading(true);
    try {
      const requestData = {
        user_id: profile.id,
        food_preferences: formData.eating_style,
        preferred_foods: formData.preferred_foods || null,
        foods_to_avoid: formData.foods_to_avoid || null,
        allergies: formData.allergies.filter((a) => a !== 'none'),
      };
      console.log('Request data:', requestData);
      
      const response = await api.post('/mealplans/generate', requestData);
      console.log('Meal plan generated:', response.data.id);

      router.replace(`/meal-detail?id=${response.data.id}`);
    } catch (error: any) {
      console.error('Generation error:', error);
      Alert.alert('Error', error.response?.data?.detail || 'Failed to generate meal plan. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Eating Style
  const renderStep1 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Eating Style</Text>
      <Text style={styles.stepSubtitle}>What type of eating style do you prefer?</Text>
      
      <ScrollView showsVerticalScrollIndicator={false}>
        {EATING_STYLES.map((style) => (
          <TouchableOpacity
            key={style.id}
            style={[styles.optionCard, formData.eating_style === style.id && styles.optionCardActive]}
            onPress={() => setFormData({ ...formData, eating_style: style.id })}
          >
            <View style={styles.optionContent}>
              <Text style={[styles.optionTitle, formData.eating_style === style.id && styles.optionTitleActive]}>
                {style.label}
              </Text>
              <Text style={styles.optionDesc}>{style.desc}</Text>
            </View>
            {formData.eating_style === style.id && (
              <Ionicons name="checkmark-circle" size={24} color={colors.primary} />
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );

  // Step 2: Preferred Foods (Optional)
  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Preferred Foods</Text>
      <Text style={styles.stepSubtitle}>Foods you'd like included in your plan (optional)</Text>
      
      <View style={styles.textInputSection}>
        <TextInput
          style={styles.textAreaInput}
          placeholder="e.g. chicken breast, rice, eggs, sweet potato"
          placeholderTextColor={colors.textMuted}
          value={formData.preferred_foods}
          onChangeText={(text) => setFormData({ ...formData, preferred_foods: text })}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
        />
        <View style={styles.hintContainer}>
          <Ionicons name="information-circle" size={16} color={colors.primary} />
          <Text style={styles.inputHint}>
            Be specific for better results: "sirloin steak" instead of "steak", "chicken breast" instead of "chicken"
          </Text>
        </View>
      </View>
    </View>
  );

  // Step 3: Foods to Avoid (Optional)
  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Foods to Avoid</Text>
      <Text style={styles.stepSubtitle}>Foods you don't want in your plan (optional)</Text>
      
      <View style={styles.textInputSection}>
        <TextInput
          style={styles.textAreaInput}
          placeholder="e.g. mushrooms, tuna, olives, seafood"
          placeholderTextColor={colors.textMuted}
          value={formData.foods_to_avoid}
          onChangeText={(text) => setFormData({ ...formData, foods_to_avoid: text })}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
        />
        <Text style={styles.inputHint}>
          These foods will be excluded from your meal plan
        </Text>
      </View>
    </View>
  );

  // Step 4: Allergies & Summary
  const renderStep4 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Allergies & Sensitivities</Text>
      <Text style={styles.stepSubtitle}>Any food allergies we should know about?</Text>
      
      <View style={styles.chipContainer}>
        {ALLERGIES.map((allergy) => (
          <TouchableOpacity
            key={allergy.id}
            style={[
              styles.chip,
              formData.allergies.includes(allergy.id) && styles.chipActive,
            ]}
            onPress={() => toggleAllergy(allergy.id)}
          >
            <Text style={[styles.chipText, formData.allergies.includes(allergy.id) && styles.chipTextActive]}>
              {allergy.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Summary */}
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>Your Personalized Meal Plan</Text>
        <View style={styles.summaryRow}>
          <Ionicons name="flame" size={18} color={colors.calories} />
          <Text style={styles.summaryText}>
            {profile?.calculated_macros?.calories || 2000} daily calories
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="barbell" size={18} color={colors.protein} />
          <Text style={styles.summaryText}>
            {profile?.calculated_macros?.protein || 150}g protein target
          </Text>
        </View>
        <View style={styles.summaryRow}>
          <Ionicons name="leaf" size={18} color={colors.carbs} />
          <Text style={styles.summaryText}>
            {EATING_STYLES.find(s => s.id === formData.eating_style)?.label || 'Balanced'} eating style
          </Text>
        </View>
        {formData.preferred_foods && (
          <View style={styles.summaryRow}>
            <Ionicons name="heart" size={18} color={colors.primary} />
            <Text style={styles.summaryText} numberOfLines={1}>
              Preferred: {formData.preferred_foods}
            </Text>
          </View>
        )}
        {formData.foods_to_avoid && (
          <View style={styles.summaryRow}>
            <Ionicons name="close-circle" size={18} color={colors.error} />
            <Text style={styles.summaryText} numberOfLines={1}>
              Avoiding: {formData.foods_to_avoid}
            </Text>
          </View>
        )}
      </View>
    </View>
  );

  const totalSteps = 4;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView 
        style={{ flex: 1 }} 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 20}
      >
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
          {Array.from({ length: totalSteps }, (_, i) => i + 1).map((s) => (
            <View key={s} style={[styles.progressDot, s <= step && styles.progressDotActive]} />
          ))}
        </View>

        <ScrollView 
          ref={scrollViewRef}
          contentContainerStyle={[styles.scrollContent, { paddingBottom: keyboardVisible ? 120 : 20 }]} 
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
          
          {/* Footer - Inside ScrollView for keyboard handling */}
          <View style={[styles.footer, keyboardVisible && styles.footerKeyboardVisible]}>
            {step > 1 && (
              <TouchableOpacity style={styles.secondaryBtn} onPress={() => { Keyboard.dismiss(); setStep(step - 1); }}>
                <Text style={styles.secondaryBtnText}>Back</Text>
              </TouchableOpacity>
            )}
            
            {step < totalSteps ? (
              <TouchableOpacity 
                style={[styles.primaryBtn, step === 1 && { flex: 1 }]} 
                onPress={() => { Keyboard.dismiss(); setStep(step + 1); }}
              >
                <Text style={styles.primaryBtnText}>Continue</Text>
                <Ionicons name="arrow-forward" size={20} color="#000" />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity 
                style={[styles.primaryBtn, styles.generateBtn]} 
                onPress={handleGenerate}
                disabled={loading || checkingSubscription}
              >
                {loading || checkingSubscription ? (
                  <ActivityIndicator color="#000" />
                ) : (
                  <>
                    <Ionicons name="sparkles" size={20} color="#000" />
                    <Text style={styles.primaryBtnText}>Generate Plan</Text>
                  </>
                )}
              </TouchableOpacity>
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
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
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
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
    backgroundColor: colors.surface,
  },
  progressDotActive: {
    backgroundColor: colors.primary,
    width: 24,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 20,
    flexGrow: 1,
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
    padding: 16,
    backgroundColor: colors.surface,
    borderRadius: 12,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  optionCardActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  optionContent: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  optionTitleActive: {
    color: colors.primary,
  },
  optionDesc: {
    fontSize: 13,
    color: colors.textMuted,
  },
  textInputSection: {
    marginTop: 8,
  },
  textAreaInput: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: colors.text,
    minHeight: 120,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputHint: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 8,
    paddingHorizontal: 4,
    flex: 1,
    marginLeft: 6,
  },
  hintContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: 10,
    paddingHorizontal: 4,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 24,
  },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 14,
    color: colors.text,
    fontWeight: '500',
  },
  chipTextActive: {
    color: '#000',
  },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  summaryText: {
    marginLeft: 10,
    fontSize: 14,
    color: colors.textSecondary,
    flex: 1,
  },
  footer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.background,
    marginTop: 20,
  },
  footerKeyboardVisible: {
    marginTop: 10,
    paddingBottom: 20,
  },
  secondaryBtn: {
    paddingVertical: 16,
    paddingHorizontal: 24,
    backgroundColor: colors.surface,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  secondaryBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  primaryBtn: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 16,
    backgroundColor: colors.primary,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  primaryBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  generateBtn: {
    backgroundColor: colors.primary,
  },
});
