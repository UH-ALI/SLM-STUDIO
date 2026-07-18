'use client';

import { useState, useEffect } from 'react';
import {
  GraduationCap,
  Briefcase,
  TrendingUp,
  HeartPulse,
  Scale,
  Globe,
  Plus,
} from 'lucide-react';
import { classNames } from '@/lib/utils';
import { Input } from '@/components/atoms/Input';
import { Textarea } from '@/components/atoms/Textarea';
import { UseCaseCard } from '@/components/molecules/UseCaseCard';
import { TeachExample } from '@/components/molecules/TeachExample';
import { Button } from '@/components/atoms/Button';
import type { FewShotExample } from '@/types/project';

const useCases = [
  { icon: GraduationCap, title: 'Education', description: 'Create tutors, teaching aids, and learning companions', value: 'education' },
  { icon: Briefcase, title: 'Business', description: 'Build customer support and business intelligence bots', value: 'business' },
  { icon: TrendingUp, title: 'Finance', description: 'Analyze reports and provide financial insights', value: 'finance' },
  { icon: HeartPulse, title: 'Medical', description: 'Medical knowledge assistants and research helpers', value: 'medical' },
  { icon: Scale, title: 'Legal', description: 'Legal research and document analysis tools', value: 'legal' },
  { icon: Globe, title: 'General', description: 'All-purpose AI assistants for any task', value: 'general' },
];

interface WizardSetupProps {
  data: {
    name: string;
    useCase: string;
    persona: string;
    fewShotExamples: FewShotExample[];
  };
  onChange: (data: WizardSetupProps['data']) => void;
  onContinue: () => void;
}

// Parse a structured persona string back into its 3 parts
function parsePersona(persona: string): { role: string; behavior: string; boundary: string } {
  const roleMatch = persona.match(/Role:\s*([\s\S]*?)(?=\nBehavior:|$)/);
  const behaviorMatch = persona.match(/Behavior:\s*([\s\S]*?)(?=\nBoundary:|$)/);
  const boundaryMatch = persona.match(/Boundary:\s*([\s\S]*?)$/);

  return {
    role: roleMatch ? roleMatch[1].trim() : '',
    behavior: behaviorMatch ? behaviorMatch[1].trim() : '',
    boundary: boundaryMatch ? boundaryMatch[1].trim() : '',
  };
}

// Combine the 3 parts into a single persona string
function buildPersona(role: string, behavior: string, boundary: string): string {
  const parts: string[] = [];
  if (role.trim()) parts.push(`Role: ${role.trim()}`);
  if (behavior.trim()) parts.push(`Behavior: ${behavior.trim()}`);
  if (boundary.trim()) parts.push(`Boundary: ${boundary.trim()}`);
  return parts.join('\n');
}

export function WizardSetup({ data, onChange, onContinue }: WizardSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Parse the existing persona into 3 fields
  const parsed = parsePersona(data.persona);
  const [role, setRole] = useState(parsed.role);
  const [behavior, setBehavior] = useState(parsed.behavior);
  const [boundary, setBoundary] = useState(parsed.boundary);

  // Sync persona fields back to the parent whenever they change
  useEffect(() => {
    const combined = buildPersona(role, behavior, boundary);
    if (combined !== data.persona) {
      onChange({ ...data, persona: combined });
    }
  }, [role, behavior, boundary]);

  const handleUseCaseSelect = (value: string) => {
    onChange({ ...data, useCase: value });
  };

  const handleExampleChange = (index: number, example: FewShotExample) => {
    const updated = [...data.fewShotExamples];
    updated[index] = example;
    onChange({ ...data, fewShotExamples: updated });
  };

  const handleAddExample = () => {
    const lastEx = data.fewShotExamples[data.fewShotExamples.length - 1];
    if (lastEx && lastEx.question.trim() && !lastEx.answer.trim()) {
      return;
    }
    onChange({
      ...data,
      fewShotExamples: [...data.fewShotExamples, { question: '', answer: '' }],
    });
  };

  const handleRemoveExample = (index: number) => {
    const updated = data.fewShotExamples.filter((_, i) => i !== index);
    onChange({ ...data, fewShotExamples: updated });
  };

  const allFewShotsValid = data.fewShotExamples.every(
    (ex) => !ex.question.trim() || ex.answer.trim().length > 0
  );

  const canContinue = 
    data.name.trim().length > 0 && 
    role.trim().length > 0 && 
    behavior.trim().length > 0 && 
    boundary.trim().length > 0 &&
    allFewShotsValid;

  const handleContinueClick = () => {
    const nextErrors: Record<string, string> = {};
    if (!data.name.trim()) {
      nextErrors.name = 'Project name is required';
    }
    if (!allFewShotsValid) {
      nextErrors.fewShot = 'If you enter a question for a few-shot example, you must also provide its answer.';
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) {
      onContinue();
    }
  };

  return (
    <div className="space-y-8">
      {/* Project Name */}
      <div>
        <h3 className="text-sm font-semibold text-ivory mb-1">Project Name</h3>
        <p className="text-xs text-fern mb-3">Give your AI assistant a name</p>
        <Input
          placeholder="e.g., Customer Support Bot"
          value={data.name}
          onChange={(e) => {
            onChange({ ...data, name: e.target.value });
            if (errors.name) setErrors({ ...errors, name: '' });
          }}
          error={errors.name}
        />
      </div>

      {/* Use Case */}
      <div>
        <h3 className="text-sm font-semibold text-ivory mb-1">Use Case</h3>
        <p className="text-xs text-fern mb-3">Select the primary purpose for your AI</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {useCases.map((uc) => (
            <UseCaseCard
              key={uc.value}
              icon={uc.icon}
              title={uc.title}
              description={uc.description}
              selected={data.useCase === uc.value}
              onClick={() => handleUseCaseSelect(uc.value)}
            />
          ))}
        </div>
      </div>

      {/* Persona — Split into 3 fields */}
      <div>
        <h3 className="text-sm font-semibold text-ivory mb-1">Persona</h3>
        <p className="text-xs text-fern mb-4">Define your AI&apos;s identity in three parts</p>

        <div className="space-y-5">
          {/* Role */}
          <div>
            <label className="block text-xs font-medium text-ivory mb-1.5">Role</label>
            <p className="text-[0.65rem] text-muted mb-2">
              What is your AI? Define its professional identity.
            </p>
            <Textarea
              placeholder="e.g., You are a professional customer support representative for a SaaS company..."
              value={role}
              onChange={(e) => setRole(e.target.value)}
              maxLength={600}
              rows={3}
            />
          </div>

          {/* Behavior */}
          <div>
            <label className="block text-xs font-medium text-ivory mb-1.5">Behavior</label>
            <p className="text-[0.65rem] text-muted mb-2">
              How should your AI communicate? Define its tone and style.
            </p>
            <Textarea
              placeholder="e.g., Be polite, clear, and concise. Use simple language. Always greet the user first..."
              value={behavior}
              onChange={(e) => setBehavior(e.target.value)}
              maxLength={600}
              rows={3}
            />
          </div>

          {/* Boundary */}
          <div>
            <label className="block text-xs font-medium text-ivory mb-1.5">Boundary</label>
            <p className="text-[0.65rem] text-muted mb-2">
              What should your AI avoid? Define its limitations and restrictions.
            </p>
            <Textarea
              placeholder="e.g., Never provide financial or legal advice. Do not share personal opinions. Redirect medical questions to a doctor..."
              value={boundary}
              onChange={(e) => setBoundary(e.target.value)}
              maxLength={600}
              rows={3}
            />
          </div>
        </div>
      </div>

      {/* Teach by Example — Dynamic */}
      <div>
        <h3 className="text-sm font-semibold text-ivory mb-1">Teach by Example</h3>
        <p className="text-xs text-fern mb-3">Provide question-answer pairs to guide your AI</p>
        <div className="space-y-4">
          {data.fewShotExamples.map((example, i) => (
            <TeachExample
              key={i}
              index={i}
              example={example}
              onChange={(ex) => handleExampleChange(i, ex)}
              onRemove={data.fewShotExamples.length > 1 ? () => handleRemoveExample(i) : undefined}
            />
          ))}
        </div>

        {/* Add Example button */}
        <button
          type="button"
          onClick={handleAddExample}
          className={classNames(
            'mt-4 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl',
            'border border-dashed border-white/[0.12] text-xs font-medium text-fern',
            'hover:text-ivory hover:border-gold/40 transition-all'
          )}
        >
          <Plus size={14} />
          Add Example
        </button>
        {errors.fewShot && <p className="text-xs text-rose mt-2">{errors.fewShot}</p>}
      </div>

      {/* Continue */}
      <div className="flex justify-end pt-4">
        <Button
          onClick={handleContinueClick}
          disabled={!canContinue}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
