/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { TextField, ListTextField } from "@web/views/fields/text/text_field";
import { CharField } from "@web/views/fields/char/char_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useEffect } from "@odoo/owl";

export class SectionAndNoteListRenderer extends ListRenderer {
    /**
     * The purpose of this extension is to allow sections and notes in the one2many list
     * primarily used on Sales Orders and Invoices
     *
     * @override
     */
    setup() {
        super.setup();
        this.titleField = "name";
        useEffect(
            (editedRecord) => this.focusToName(editedRecord),
            () => [this.editedRecord]
        )
    }

    focusToName(editRec) {
        if (editRec && editRec.isNew && this.isSectionOrNote(editRec)) {
            const col = this.state.columns.find((c) => c.name === this.titleField);
            this.focusCell(col, null);
        }
    }

    isSectionOrNote(record=null) {
        record = record || this.record;
        return ['line_section', 'line_note'].includes(record.data.display_type);
    }

    getRowClass(record) {
        const existingClasses = super.getRowClass(record);
        return `${existingClasses} o_is_${record.data.display_type} one2many_width`;
    }

    getCellClass(column, record) {
        const classNames = super.getCellClass(column, record);
        if (this.isSectionOrNote(record) && column.widget !== "handle" && column.name !== this.titleField && column.name !== "is_delete" && column.name !== "create_qty_computation") {
            return `${classNames} o_hidden`;
        }
        return classNames;
    }

    getColumns(record) {
        const columns = super.getColumns(record);
        if (this.isSectionOrNote(record)) {
            return this.getSectionColumns(columns);
        }
        return columns;
    }

    getSectionColumns(columns) {
        const sectionCols = columns.filter((col) => col.widget === "handle" || col.type === "field" && (col.name === this.titleField || col.name === "is_delete" || col.name === "create_qty_computation"));        
        return sectionCols.map((col) => {
            if (col.name === this.titleField) {
                return { ...col, colspan: columns.length - sectionCols.length + 1 };
            } else {
                return { ...col };
            }
        });
    }
}
SectionAndNoteListRenderer.template = "account.sectionAndNoteListRenderer";

export class SectionAndNoteFieldOne2Many extends X2ManyField {}
SectionAndNoteFieldOne2Many.components = {
    ...X2ManyField.components,
    ListRenderer: SectionAndNoteListRenderer,
};

export class SectionAndNoteText extends Component {
    static props = { ...standardFieldProps };

    get componentToUse() {
        return this.props.record.data.display_type === 'line_section' ? CharField : TextField;
    }
}
SectionAndNoteText.template = "account.SectionAndNoteText";

export class ListSectionAndNoteText extends SectionAndNoteText {
    get componentToUse() {
        return this.props.record.data.display_type !== "line_section"
            ? ListTextField
            : super.componentToUse;
    }
}

export const sectionAndNoteFieldOne2Many = {
    ...x2ManyField,
    component: SectionAndNoteFieldOne2Many,
    additionalClasses: [...x2ManyField.additionalClasses || [], "o_field_one2many"],
};

export const sectionAndNoteText = {
    component: SectionAndNoteText,
    additionalClasses: ["o_field_text"],
};

export const listSectionAndNoteText = {
    ...sectionAndNoteText,
    component: ListSectionAndNoteText,
};

registry.category("fields").add("ns_boq_section_and_note_one2many", sectionAndNoteFieldOne2Many);
registry.category("fields").add("ns_boq_section_and_note_text", sectionAndNoteText);
registry.category("fields").add("list.ns_boq_section_and_note_text", listSectionAndNoteText);
