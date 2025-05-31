/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class BoqListController extends ListController {
   setup() {
       super.setup();
   }
   UploadBoq() {
       this.actionService.doAction({
          type: 'ir.actions.act_window',
          res_model: 'boq.csv.upload.wizard',
          name:'Upload BOQ',
          view_mode: 'form',
          view_type: 'form',
          views: [[false, 'form']],
          target: 'new',
          res_id: false,
      });
   }
}
registry.category("views").add("upload_button_in_tree", {
   ...listView,
   Controller: BoqListController,
   buttonTemplate: "boq_custom.ListView.Buttons",
});