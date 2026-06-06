import { FilesIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import { useI18n } from "@/core/i18n/hooks";

import { useArtifacts } from "./context";

export const ArtifactTrigger = () => {
  const { t } = useI18n();
  const { artifacts, setOpen: setArtifactsOpen } = useArtifacts();

  if (!artifacts || artifacts.length === 0) {
    return null;
  }
  return (
    <Tooltip content="Show artifacts of this conversation">
      <Button
        className="nail-outline-button h-9 rounded-full px-3 text-xs font-semibold"
        variant="ghost"
        onClick={() => {
          setArtifactsOpen(true);
        }}
      >
        <FilesIcon />
        {t.common.artifacts}
      </Button>
    </Tooltip>
  );
};
