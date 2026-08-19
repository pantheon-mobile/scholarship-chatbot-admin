import { Button, Modal } from "@/components/admin";
import { FaqDetail } from "@/types/faq";
import { FaqClassificationType } from "@/types/faqClassification";
import { LinkedPlainText } from "./LinkedPlainText";
import styles from "./FaqReferenceModal.module.css";

type FaqReferenceModalProps = {
  open: boolean;
  detail: FaqDetail | null;
  classificationTypes: FaqClassificationType[];
  loading: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
};

function formatJst(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function FaqReferenceModal({
  open, detail, classificationTypes, loading, busy, error, onClose, onEdit, onDelete,
}: FaqReferenceModalProps) {
  const selected = Object.fromEntries((detail?.classifications ?? []).map((item) => [item.type_code, item.value_name]));
  const typeMap = Object.fromEntries(classificationTypes.map((type) => [type.type_code, type.display_label]));
  const similarQuestions = [...(detail?.similar_questions ?? [])].sort((left, right) => left.display_order - right.display_order);

  return <Modal
    open={open}
    title="FAQ参照"
    size="wide"
    showCloseButton
    busy={busy}
    closeOnBackdrop={!busy}
    closeOnEscape={!busy}
    error={error}
    onClose={onClose}
    footer={<>
      <Button className={styles.footerButton} variant="secondary" onClick={onClose} disabled={busy}>閉じる</Button>
      <Button className={styles.footerButton} variant="primary" onClick={onEdit} disabled={busy || loading || !detail}>編集する</Button>
      <Button className={styles.footerButton} variant="danger" onClick={onDelete} disabled={busy || loading || !detail}>削除する</Button>
    </>}
  >
    {loading ? <div className={styles.loading}>読み込み中...</div> : detail && <div className={styles.details}>
      <div className={styles.row}><div className={styles.label}>ID</div><div className={styles.value}>{detail.id}</div></div>
      <div className={styles.row}><div className={styles.label}>質問</div><div className={`${styles.value} ${styles.preWrap}`}>{detail.question}</div></div>
      <div className={styles.row}><div className={styles.label}>回答</div><div className={`${styles.value} ${styles.preWrap}`}><LinkedPlainText text={detail.answer} /></div></div>
      <div className={styles.row}><div className={styles.label}>同じ回答の類似質問</div><div className={`${styles.value} ${styles.similarList}`}>{similarQuestions.map((item) => <div className={styles.preWrap} key={item.id}>{item.question}</div>)}</div></div>
      {[1,2,3,4].map((index) => <div className={styles.row} key={index}>
        <div className={styles.label}>{typeMap[`FAQ_TYPE_${index}`] ?? `区分${index}`}</div>
        <div className={styles.value}>{selected[`FAQ_TYPE_${index}`] ?? ""}</div>
      </div>)}
      <div className={styles.row}><div className={styles.label}>チャット利用</div><div className={styles.value}>{detail.chat_enabled ? "公開" : "非公開"}</div></div>
      <div className={styles.row}><div className={styles.label}>最終更新日時</div><div className={styles.value}>{formatJst(detail.updated_at)}</div></div>
    </div>}
  </Modal>;
}
