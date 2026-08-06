import { forwardRef, InputHTMLAttributes, useEffect, useImperativeHandle, useRef } from "react";

type CheckboxProps = InputHTMLAttributes<HTMLInputElement> & { indeterminate?: boolean };

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { indeterminate = false, ...props }, forwardedRef,
) {
  const localRef = useRef<HTMLInputElement>(null);
  useImperativeHandle(forwardedRef, () => localRef.current as HTMLInputElement);
  useEffect(() => {
    if (localRef.current) localRef.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return <input {...props} ref={localRef} type="checkbox" />;
});
