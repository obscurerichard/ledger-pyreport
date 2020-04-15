/*
    ledger-pyreport
    Copyright © 2020  Lee Yingtong Li (RunasSudo)
 
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
 
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.
 
    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

// Consider replacing this when the Clipboard API has better availability
function copyText(text) {
	var ta = document.createElement('textarea');
	ta.value = text;
	ta.style = 'position: fixed; top: 0; left: 0;'; // Avoid scrolling
	document.body.appendChild(ta);
	ta.select();
	document.execCommand('copy');
	document.body.removeChild(ta);
}

document.querySelectorAll('.copyable-amount').forEach(function(el) {
	el.addEventListener('click', function() {
		copyText(el.getAttribute('title'));
		showToast('Amount was copied to the clipboard');
	});
});
