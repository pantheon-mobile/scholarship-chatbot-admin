"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  AdminIcon, AdminLayout, Breadcrumb, Button, CharacterCountTextarea, Modal, SelectField, ToggleSwitch,
} from "@/components/admin";
import { fetchFaqClassifications } from "@/lib/faqClassificationsApi";
import { createFaq } from "@/lib/faqsApi";
import { FaqClassificationType } from "@/types/faqClassification";
import { FaqApiError } from "@/types/faq";
import styles from "./page.module.css";

type FormValues = {
  question: string;
  answer: string;
  similarQuestions: string[];
  classification_1_value_id: string;
  classification_2_value_id: string;
  classification_3_value_id: string;
  classification_4_value_id: string;
  chat_enabled: boolean;
};

const initialValues: FormValues = {
  question: "", answer: "", similarQuestions: [], classification_1_value_id: "",
  classification_2_value_id: "", classification_3_value_id: "", classification_4_value_id: "", chat_enabled: true,
};

export default function FaqNewPage() {
  const router = useRouter();
  const [values, setValues] = useState<FormValues>(initialValues);
  const [types, setTypes] = useState<FaqClassificationType[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  const typeMap = useMemo(() => Object.fromEntries(types.map((type) => [type.type_code, type])), [types]);

  const currentErrors = useMemo(() => {
    const next: Record<string, string> = {};
    if (!values.question.trim()) next.question = "質問を入力してください。";
    else if (values.question.trim().length > 500) next.question = "質問は500文字以内で入力してください。";
    if (!values.answer.trim()) next.answer = "回答を入力してください。";
    else if (values.answer.trim().length > 1000) next.answer = "回答は1000文字以内で入力してください。";
    values.similarQuestions.forEach((value, index) => {
      if (!value.trim()) next[`similar-${index}`] = "類似質問を入力してください。";
      else if (value.trim().length > 500) next[`similar-${index}`] = "類似質問は500文字以内で入力してください。";
    });
    return next;
  }, [values]);
  const canSubmit = Object.keys(currentErrors).length === 0 && !busy;

  useEffect(() => {
    fetchFaqClassifications().then(setTypes).catch(() => setError("区分の取得に失敗しました。"));
  }, []);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const setValue = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    if (busy) return;
    setValues((current) => ({ ...current, [key]: value }));
    setError(null);
    setFieldErrors({});
  };
  const requestNavigate = (path: string) => {
    if (busy) return;
    if (dirty) setPendingPath(path);
    else router.push(path);
  };
  const touch = (key: string) => setTouched((current) => new Set(current).add(key));
  const addSimilarQuestion = () => setValue("similarQuestions", [...values.similarQuestions, ""]);
  const updateSimilarQuestion = (index: number, value: string) => setValue(
    "similarQuestions", values.similarQuestions.map((item, itemIndex) => itemIndex === index ? value : item),
  );
  const removeSimilarQuestion = (index: number) => setValue(
    "similarQuestions", values.similarQuestions.filter((_, itemIndex) => itemIndex !== index),
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) {
      setTouched(new Set(["question", "answer", ...values.similarQuestions.map((_, index) => `similar-${index}`)]));
      return;
    }
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      await createFaq({
        question: values.question.trim(), answer: values.answer.trim(),
        similar_questions: values.similarQuestions.map((value) => value.trim()),
        classification_1_value_id: values.classification_1_value_id ? Number(values.classification_1_value_id) : null,
        classification_2_value_id: values.classification_2_value_id ? Number(values.classification_2_value_id) : null,
        classification_3_value_id: values.classification_3_value_id ? Number(values.classification_3_value_id) : null,
        classification_4_value_id: values.classification_4_value_id ? Number(values.classification_4_value_id) : null,
        chat_enabled: values.chat_enabled,
      });
      setValues(initialValues);
      router.push("/faqs");
    } catch (reason) {
      if (reason instanceof FaqApiError) {
        const field = reason.code?.startsWith("FAQ_QUESTION_") ? "question" : reason.code?.startsWith("FAQ_ANSWER_") ? "answer" : reason.code?.startsWith("FAQ_SIMILAR_QUESTION_") ? "similar-0" : null;
        if (field) setFieldErrors({ [field]: reason.message });
        else setError(reason.message);
      } else setError(reason instanceof Error ? reason.message : "FAQの登録に失敗しました。");
    } finally { setBusy(false); }
  };

  return <AdminLayout activeMenu="faq" contentWidth="wide" contentAlign="start" onNavigate={requestNavigate}>
    <form className={styles.page} onSubmit={submit}>
      <div className={styles.topRow}>
        <Breadcrumb items={[{ label: "FAQ一覧", onClick: () => requestNavigate("/faqs") }, { label: "FAQ登録" }]} />
        <Button variant="secondary" icon={<AdminIcon name="back" size={19} />} onClick={() => requestNavigate("/faqs")} disabled={busy}>FAQ一覧へ戻る</Button>
      </div>
      <div className={styles.divider} />
      {error && <div className={styles.error} role="alert">{error}</div>}

      <div className={styles.formRows}>
        <div className={styles.formRow}><span className={styles.rowLabel}>ID：</span><span className={styles.idValue}>－</span></div>
        <div className={`${styles.formRow} ${styles.textareaRow}`}>
          <span className={styles.rowLabel}>質問（必須）：</span>
          <CharacterCountTextarea aria-label="質問" wrapperClassName={styles.questionField} value={values.question} maxLength={500} disabled={busy} error={(touched.has("question") && currentErrors.question) || fieldErrors.question} onBlur={() => touch("question")} onChange={(event) => setValue("question", event.target.value)} />
        </div>
        <div className={`${styles.formRow} ${styles.textareaRow}`}>
          <span className={styles.rowLabel}>回答（必須）：</span>
          <CharacterCountTextarea aria-label="回答" wrapperClassName={styles.answerField} textareaClassName={styles.answerTextarea} value={values.answer} maxLength={1000} disabled={busy} error={(touched.has("answer") && currentErrors.answer) || fieldErrors.answer} onBlur={() => touch("answer")} onChange={(event) => setValue("answer", event.target.value)} />
        </div>

        <div className={`${styles.formRow} ${styles.similarRow}`}>
          <span className={styles.rowLabel}>類似質問：</span>
          <div className={styles.similarFields}>
            {values.similarQuestions.map((value, index) => <div className={styles.similarItem} key={index}>
              <CharacterCountTextarea aria-label={`類似質問${index + 1}`} wrapperClassName={styles.similarField} textareaClassName={styles.similarTextarea} value={value} maxLength={500} disabled={busy} error={(touched.has(`similar-${index}`) && currentErrors[`similar-${index}`]) || fieldErrors[`similar-${index}`]} onBlur={() => touch(`similar-${index}`)} onChange={(event) => updateSimilarQuestion(index, event.target.value)} />
              <Button variant="text" focusTone="danger" icon={<AdminIcon name="close" size={18} />} disabled={busy} onClick={() => removeSimilarQuestion(index)}>削除</Button>
            </div>)}
            <Button className={styles.addSimilar} variant="add" icon={<AdminIcon name="plus" size={19} />} disabled={busy} onClick={addSimilarQuestion}>類似質問を追加</Button>
          </div>
        </div>

        {[1,2,3,4].map((index) => {
          const type = typeMap[`FAQ_TYPE_${index}`];
          const key = `classification_${index}_value_id` as "classification_1_value_id" | "classification_2_value_id" | "classification_3_value_id" | "classification_4_value_id";
          return <div className={styles.formRow} key={index}>
            <span className={styles.rowLabel}>{type?.display_label ?? `区分${index}`}：</span>
            <SelectField wrapperClassName={styles.classificationField} aria-label={type?.display_label ?? `区分${index}`} value={values[key]} disabled={busy} onChange={(event) => setValue(key, event.target.value)}>
              <option value="">未選択</option>{type?.values.map((value) => <option key={value.id} value={value.id}>{value.value_name}</option>)}
            </SelectField>
          </div>;
        })}
        <div className={`${styles.formRow} ${styles.toggleRow}`}>
          <span className={styles.rowLabel}>チャット利用：</span>
          <ToggleSwitch checked={values.chat_enabled} checkedLabel="公開" uncheckedLabel="非公開" disabled={busy} onChange={(value) => setValue("chat_enabled", value)} />
        </div>
      </div>

      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={!canSubmit}>{busy ? "登録中..." : "登録する"}</Button>
        <Button variant="secondary" onClick={() => requestNavigate("/faqs")} disabled={busy}>キャンセル</Button>
      </div>
    </form>
    <Modal open={Boolean(pendingPath)} title="確認" confirmLabel="移動する" busy={busy} closeOnBackdrop={!busy} closeOnEscape={!busy} onClose={() => { if (!busy) setPendingPath(null); }} onConfirm={() => {
      if (busy || !pendingPath) return;
      const path = pendingPath;
      setPendingPath(null);
      setValues(initialValues);
      router.push(path);
    }}>{pendingPath === "/faqs" ? "FAQを登録せずにFAQ一覧に戻ります。よろしいですか？" : "入力内容を保存せずに移動します。よろしいですか？"}</Modal>
  </AdminLayout>;
}
