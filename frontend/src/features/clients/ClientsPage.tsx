import { ArrowRight, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader } from "@/features/common/PageHeader";
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";

import { useListClientsQuery } from "./clientsApi";
import { LinkRow } from "@/features/common/LinkRow";

// **Find a beneficiary — nothing else** (§8, UC-026). A person is created only by the Step-1 intake
// form, and edited from inside their own case, so this screen neither creates, edits nor deletes;
// the API refuses all three regardless (§7.2). Each row links to that person's case, which is what
// a lawyer searching for someone is actually looking for.
export function ClientsPage() {
  const { t } = useTranslation();
  const [term, setTerm] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useListClientsQuery({ search, page });

  // Debounce the search box so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setSearch(term.trim()), 300);
    return () => clearTimeout(id);
  }, [term]);

  // A new search resets to the first page (its result set is different).
  useEffect(() => setPage(1), [search]);

  const rows = data?.results ?? [];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader title={t("clients.title")} description={t("clients.subtitle")} />

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="ps-9"
          placeholder={t("clients.searchPlaceholder")}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
        />
      </div>

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("clients.fullName")}</TableHead>
              <TableHead>{t("clients.pid")}</TableHead>
              <TableHead>{t("clients.motherName")}</TableHead>
              <TableHead>{t("clients.maritalStatus")}</TableHead>
              <TableHead className="w-32 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={5}
              isLoading={isLoading}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("clients.empty")}
              onRetry={refetch}
              skeletonRows={4}
            />
            {!isLoading &&
              !isError &&
              rows.map((client) => (
                <LinkRow key={client.id} to={`/processes?search=${encodeURIComponent(client.pid)}`}>
                  <TableCell className="font-medium">{client.full_name}</TableCell>
                  <TableCell dir="ltr" className="text-start">
                    {client.pid}
                  </TableCell>
                  <TableCell>{client.mother_full_name}</TableCell>
                  <TableCell>
                    <Badge variant="neutral">{t(`clients.marital.${client.marital_status}`)}</Badge>
                  </TableCell>
                  <TableCell className="text-end">
                    {/* Filtered by PID rather than a process id: the client payload carries no
                        case reference, and the Processes search matches a national ID (UC-005). */}
                    <Button asChild variant="ghost" size="sm">
                      <Link to={`/processes?search=${encodeURIComponent(client.pid)}`}>
                        {t("clients.viewCase")}
                        <ArrowRight className="size-4 rtl:rotate-180" />
                      </Link>
                    </Button>
                  </TableCell>
                </LinkRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <Pagination page={page} count={data?.count ?? 0} onPage={setPage} />
    </div>
  );
}
